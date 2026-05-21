# Deployment: Helm

This runbook covers installing `document-viewer` into Kubernetes via the
Helm chart in `helm/document-viewer/`. The chart deploys an API
Deployment, a worker Deployment, a Gotenberg Deployment with a
NetworkPolicy, optional in-chart Redis, a ConfigMap, a Secret, and an
optional ServiceMonitor.

## Prerequisites

- Kubernetes 1.27+.
- Helm 3.13+.
- A container registry holding the API and worker images, accessible from
  the cluster.
- An external Redis (recommended for production) or accept the bundled
  single-pod Redis (`redis.embedded: true`).
- A reachable S3 endpoint (or `SOURCE_BACKEND=fs` with an appropriately
  mounted PVC; not covered here).

## Install

Copy the example values file and edit it:

```bash
cp helm/document-viewer/values.example.yaml my-values.yaml
$EDITOR my-values.yaml
```

The fields you almost always need to change:

- `image.repository` (replace `OWNER/document-viewer`)
- `image.tag` (the app version you want to install)
- `gotenberg.image` (replace `sha256:CHANGE-ME` with the real digest;
  obtain it with `docker buildx imagetools inspect gotenberg/gotenberg:8`)
- `config.s3Endpoint`, `config.s3Bucket`, `config.s3Region`
- `secrets.jwtPublicKey`, `secrets.s3AccessKeyId`, `secrets.s3SecretAccessKey`
- `api.ingress.host`

Install:

```bash
helm install document-viewer ./helm/document-viewer -f my-values.yaml
```

For sensitive values that you do not want in `my-values.yaml`, pass them at
install time with `--set-file`:

```bash
helm install document-viewer ./helm/document-viewer \
  -f my-values.yaml \
  --set-file secrets.jwtPublicKey=./jwt-public.pem
```

## Private registries

If the API/worker images are in a private registry, create a pull secret
and reference it from the service account or attach it via a values
override:

```bash
kubectl create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username='<user>' \
  --docker-password='<pat>'
```

The chart templates do not currently take an `imagePullSecrets` value at
the top level; add the secret to the default service account in the target
namespace (`kubectl patch serviceaccount default ...`) or fork the chart
to add an `imagePullSecrets` block on each deployment.

## NetworkPolicy compatibility

The chart ships `gotenberg-networkpolicy.yaml`. It restricts Gotenberg
pods to ingress from worker pods only on TCP/3000 and denies all egress.

NetworkPolicies are only enforced when the cluster runs a CNI that
implements them (Calico, Cilium, Antrea, etc.). On clusters with a CNI
that ignores NetworkPolicies (some managed Kubernetes flavors with the
default networking add-on, kind without an explicit CNI), the policy is
silently a no-op. Treat this as a hardening defense in depth, not the
only network control:

- Run the viewer in its own namespace.
- Apply default-deny ingress/egress at the namespace level via a separate
  policy if the cluster supports it.
- For clusters without NetworkPolicy enforcement, use a service mesh or
  cluster-level firewall rules to confine egress from Gotenberg pods.

## Verify

After install, check the rollouts:

```bash
kubectl rollout status deploy/document-viewer-api
kubectl rollout status deploy/document-viewer-worker
kubectl rollout status deploy/document-viewer-gotenberg
```

If `redis.embedded: true`, also:

```bash
kubectl rollout status deploy/document-viewer-redis
```

Smoke-test the API with a port-forward:

```bash
kubectl port-forward svc/document-viewer-api 8000:8000 &
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
```

`/healthz` is the liveness probe target (no Redis check). `/readyz`
returns `200` only after the API can ping Redis.

## Backups

There is nothing to back up by design. Sources live in S3 (managed
independently); the Redis cache is ephemeral; API and worker pods are
stateless. If you ran with `redis.embedded: true` in production you can
optionally back up its `dump.rdb` to preserve warm caches across
upgrades, but it is not required.

## Log shipping

Both API and worker write structured JSON logs to stdout. Use the cluster's
existing log shipping (Fluent Bit DaemonSet, Vector agent, Loki Promtail,
the cloud provider's logging integration). The chart does not bundle a log
shipper; that is a cluster-wide concern.

## Secrets handling

Do not check the actual secret values into Git. Several mature options are
available:

- **Sealed Secrets** (Bitnami): encrypt secret values into a
  `SealedSecret` CRD checked into Git. The controller in the cluster
  decrypts them into a regular `Secret`. Point the chart at the
  decrypted `Secret` name by adjusting `templates/secret.yaml` or by
  pre-creating the secret and skipping the chart-managed one (fork
  needed).
- **External Secrets Operator (ESO)**: fetch secret values from AWS
  Secrets Manager, Vault, Google Secret Manager, etc. The chart's
  `Secret` resource can be replaced by an `ExternalSecret` that targets
  the same name and keys (`JWT_PUBLIC_KEY`, `S3_ACCESS_KEY_ID`,
  `S3_SECRET_ACCESS_KEY`).
- **CSI Secret Store driver**: mount secrets directly from a
  provider-backed CSI volume. Requires more chart surgery; rarely needed
  for three secrets.

Whichever path you pick, the deployments expect a Secret named
`{{ .Release.Name }}-secrets` with keys `JWT_PUBLIC_KEY`,
`S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`. Match those names.

## Rotation

### JWT public key (RS256)

1. The back-office issuer rotates its signing key and publishes the new
   public key.
2. Update the value at `secrets.jwtPublicKey` (or the upstream secret
   store that ESO/Sealed Secrets reads from).
3. `helm upgrade document-viewer ./helm/document-viewer -f my-values.yaml`
4. The API deployment rolls and starts verifying with the new key.

### S3 credentials

1. Issue new keys.
2. Update `secrets.s3AccessKeyId` and `secrets.s3SecretAccessKey`.
3. `helm upgrade` — only worker pods need to recreate (they hold the S3
   credentials), but a rolling restart of all consumers of the Secret is
   safe.
4. Revoke the old keys.

## Uninstall

```bash
helm uninstall document-viewer
```

This removes everything the chart created. It does not touch the S3
bucket or any externally managed Redis.

## Upgrades

See [upgrades.md](upgrades.md) for the chart/app/Gotenberg compatibility
matrix. For routine upgrades:

```bash
helm repo update         # if installing from a chart repo
helm upgrade document-viewer ./helm/document-viewer -f my-values.yaml
kubectl rollout status deploy/document-viewer-api
```
