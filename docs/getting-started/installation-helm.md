# Install with Helm

This page covers deploying `document-viewer` to a Kubernetes cluster using the Helm chart at [`helm/document-viewer/`](../../helm/document-viewer/).

## Prerequisites

- Kubernetes 1.27 or newer. The chart uses no APIs deprecated past 1.27.
- `kubectl` and `helm` 3.12+ on your workstation.
- A working **ingress controller**. The default `values.yaml` assumes `ingressClassName: nginx`; ingress-nginx, Traefik, HAProxy, and most managed offerings work the same way.
- A **CNI that enforces NetworkPolicy**. Calico, Cilium, Antrea, AWS VPC CNI with policy mode, and Azure CNI Overlay all qualify. Without an enforcing CNI, the chart's NetworkPolicy resources install but do not isolate anything - see the [NetworkPolicy compatibility](#networkpolicy-compatibility) note below.
- Optional but recommended: **cert-manager** for automatic TLS certificates on the ingress.
- Optional: the **Prometheus Operator** (`kube-prometheus-stack` or similar) if you want the chart's `ServiceMonitor`.
- An S3-compatible bucket and credentials with read-only access to the document prefix.
- A JWT signer in the back-office. RS256 is recommended in production; you provide the public key, the private key never leaves the signer.

## Repository layout that matters

- [`helm/document-viewer/Chart.yaml`](../../helm/document-viewer/Chart.yaml) - chart metadata.
- [`helm/document-viewer/values.yaml`](../../helm/document-viewer/values.yaml) - defaults.
- [`helm/document-viewer/values.example.yaml`](../../helm/document-viewer/values.example.yaml) - annotated example showing the fields you usually override.
- [`helm/document-viewer/templates/`](../../helm/document-viewer/templates/) - the rendered manifests, including the Gotenberg NetworkPolicy.

## Quick install

From the repository root:

```bash
helm install document-viewer ./helm/document-viewer \
  --namespace document-viewer \
  --create-namespace \
  --values my-values.yaml
```

Where `my-values.yaml` is your environment overlay - see the sample below.

## Sample `values.yaml`

The snippet below is a realistic production overlay. Start from `values.example.yaml` and trim what you do not need.

```yaml
image:
  registry: ghcr.io
  repository: your-org/document-viewer
  tag: "0.1.0"
  pullPolicy: IfNotPresent

api:
  replicas: 2
  resources:
    requests: { cpu: 100m, memory: 256Mi }
    limits:   { cpu: 1000m, memory: 1Gi }
  service:
    type: ClusterIP
    port: 8000
  ingress:
    enabled: true
    className: nginx
    host: viewer.example.com
    tls: true

worker:
  replicas: 3
  concurrency: 4
  resources:
    requests: { cpu: 250m, memory: 512Mi }
    limits:   { cpu: 2000m, memory: 2Gi }
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 12
    targetCPUUtilizationPercentage: 70

gotenberg:
  # Pin to a digest in production; the placeholder must be replaced before release.
  image: gotenberg/gotenberg:8@sha256:REPLACE-WITH-A-REAL-DIGEST
  replicas: 2
  resources:
    requests: { cpu: 500m, memory: 1Gi }
    limits:   { cpu: 2000m, memory: 2Gi }

redis:
  # `embedded: true` runs a single in-chart Redis. Set false and point
  # the env vars at an external Redis for HA.
  embedded: true
  image: redis:7-alpine

config:
  jwtAlgorithm: RS256
  jwtRequiredIss: back-office
  sourceBackend: s3
  s3Endpoint: "https://s3.eu-west-1.amazonaws.com"
  s3Bucket: "kyc-docs"
  s3Region: eu-west-1
  cacheTtlSeconds: 900
  maxSourceBytes: 104857600
  maxPages: 500
  maxPageWidth: 2400

secrets:
  # Provide via --set-file or a sealed-secrets / external-secrets pipeline.
  jwtPublicKey: ""
  s3AccessKeyId: ""
  s3SecretAccessKey: ""

monitoring:
  serviceMonitor:
    enabled: true
    namespace: monitoring
    interval: 30s
```

### TLS via cert-manager

If you run cert-manager, annotate the ingress so it requests a certificate automatically. Add this to your overlay's `api.ingress` section:

```yaml
api:
  ingress:
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod
```

The chart wires the `tls` block to a secret named `<release>-api-tls`. cert-manager will populate it.

### Providing secrets safely

Do not check secret values into git. Two common patterns:

```bash
# Inline at install time (still readable by anyone with cluster access to the Secret):
helm install document-viewer ./helm/document-viewer \
  --namespace document-viewer \
  --values my-values.yaml \
  --set-file secrets.jwtPublicKey=./back-office.pub.pem \
  --set secrets.s3AccessKeyId="$S3_KEY" \
  --set secrets.s3SecretAccessKey="$S3_SECRET"
```

```yaml
# Or rely on external-secrets / sealed-secrets and leave secrets.* empty in values.yaml.
# The chart's Secret template only creates entries for non-empty fields, so the
# external operator can manage the Secret object directly without conflict.
```

### External Redis

Set `redis.embedded: false` and override the URL via the configmap. The chart writes `REDIS_URL` from `config.redisUrl` when provided; otherwise it points the workloads at the in-chart Redis service. For a managed Redis:

```yaml
redis:
  embedded: false
config:
  redisUrl: redis://your-redis.cache.amazonaws.com:6379/0
```

## NetworkPolicy compatibility

The chart ships [`gotenberg-networkpolicy.yaml`](../../helm/document-viewer/templates/gotenberg-networkpolicy.yaml), which:

- Allows ingress to the Gotenberg pods **only** from worker pods on TCP/3000.
- Sets `egress: []` (i.e. default-deny), so Gotenberg cannot reach the internet, the cluster API server, or any other service.

This relies on your CNI enforcing NetworkPolicy. Verify with:

```bash
kubectl get networkpolicies -n document-viewer
kubectl describe networkpolicy document-viewer-gotenberg -n document-viewer
```

If your CNI does **not** enforce NetworkPolicy (vanilla Flannel, kindnet, etc.), the policy object is silently inert. Either switch to an enforcing CNI before going to production, or rely on a separate egress-blocking mechanism (e.g. Istio AuthorizationPolicy, a managed firewall). The Gotenberg pod still runs read-only with all capabilities dropped, so a compromise has no network exit, but the lateral-movement guarantee depends on policy enforcement.

If you also want to clamp the worker and api pods (recommended), add your own NetworkPolicies in the same namespace.

## Verifying the deployment

```bash
helm install document-viewer ./helm/document-viewer \
  --namespace document-viewer \
  --create-namespace \
  --values my-values.yaml

kubectl rollout status deployment/document-viewer-api      -n document-viewer
kubectl rollout status deployment/document-viewer-worker   -n document-viewer
kubectl rollout status deployment/document-viewer-gotenberg -n document-viewer
```

Each command exits 0 once the rollout converges. Then sanity-check the API:

```bash
kubectl -n document-viewer port-forward svc/document-viewer-api 8000:8000
curl -sS http://localhost:8000/healthz
curl -sS http://localhost:8000/readyz
```

`/readyz` returns 200 only when Redis is reachable. Once your ingress is up, the same endpoints answer at `https://viewer.example.com/healthz`.

## Upgrading

```bash
helm upgrade document-viewer ./helm/document-viewer \
  --namespace document-viewer \
  --values my-values.yaml
```

The api and worker `Deployment`s use a rolling update strategy; existing cache entries become stale and renew on the next page request. Check `docs/operations/upgrades.md` for the compatibility matrix between chart version, app version, and the pinned Gotenberg digest.

## Uninstalling

```bash
helm uninstall document-viewer --namespace document-viewer
kubectl delete namespace document-viewer
```

No persistent volumes are claimed by the chart - by design, the service is stateless. Source documents stay in S3; cache entries vanish with Redis.
