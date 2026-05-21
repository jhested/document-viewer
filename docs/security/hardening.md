# Production hardening checklist

This is the deployment-time checklist. The Helm chart ships sensible defaults
for most of the in-cluster controls (`runAsNonRoot`, `readOnlyRootFilesystem`,
`capabilities.drop: [ALL]`, a default-deny NetworkPolicy on Gotenberg), but
several items require operator action before a production rollout.

Treat unchecked items as blockers. Companion reading:
[`threat-model.md`](threat-model.md) explains *why* each control exists.

## Identity and tokens

- [ ] **Pick the right JWT algorithm for your environment.**
  - RS256 (default in the chart) — back-office signs with a private key; viewer
    holds only the public key. Use this if the back-office and viewer are
    operated by different teams or live in different trust domains.
  - HS256 — shared secret. Acceptable for single-tenant deployments where the
    same team operates both sides.
- [ ] **Rotate the JWT signing material on a schedule.**
  - HS256 secret: rotate **quarterly**, minimum.
  - RS256 keypair: rotate **annually**, minimum. Use a key-id (`kid`) header and
    keep the previous public key in the verifier for the overlap window.
- [ ] **Set `JWT_REQUIRED_ISS`.** Never accept tokens with a missing or
  unexpected `iss`.
- [ ] **Keep token TTLs short.** 5–15 minutes is the design target. The replay
  guard's Redis TTL tracks `exp - now`, so over-long TTLs both expand the
  replay window and bloat Redis.
- [ ] **Never log a full JWT.** Audit logs include `sub`, `case`, `jti`, and
  request ID — never the raw token. Strip the token from any log lines you add.
- [ ] **Optional ingress-level JWT validator** (oauth2-proxy, Traefik plugin,
  nginx `auth_jwt`, Istio request authentication). The API still validates
  again — this is defense in depth and does not replace API validation.

## Network policy and namespace topology

- [ ] **Run the viewer in its own Kubernetes namespace**, separate from the
  back-office and any other workload. Apply namespace-scoped RBAC.
- [ ] **Add a default-deny NetworkPolicy** to the viewer namespace. The chart
  only ships NetworkPolicy for Gotenberg; api and worker need cluster-wide
  policy from the operator:

  ```yaml
  apiVersion: networking.k8s.io/v1
  kind: NetworkPolicy
  metadata:
    name: default-deny
    namespace: viewer
  spec:
    podSelector: {}
    policyTypes: [Ingress, Egress]
  ```

  Then layer allow-rules:
  - `viewer-api` ingress: from the ingress controller only; egress: Redis only.
  - `viewer-worker` egress: Redis, S3 endpoint, Gotenberg only. No general
    internet egress.
  - `viewer-gotenberg` (already shipped): ingress from `viewer-worker` only,
    egress `[]` (default-deny).
- [ ] **Restrict ingress to corporate VPN, zero-trust proxy, or BeyondCorp-style
  gateway.** The viewer is not designed to be exposed to the public internet,
  even with JWT auth. Use mTLS or device-bound access at the edge.
- [ ] **Verify Redis is on a private network**, never exposed via ClusterIP that
  other namespaces can reach. The embedded Redis in the chart is fine for
  development; production deployments should use a managed or dedicated Redis
  with auth (`requirepass`) and TLS.

## Container and image supply chain

- [ ] **Pull all images by digest, not tag.** The chart's
  `values.yaml:gotenberg.image` defaults to
  `gotenberg/gotenberg:8@sha256:CHANGE-ME`. The operator **must** replace
  `CHANGE-ME` with a real digest before deploy. Pinning by tag means an
  upstream re-tag changes what runs without your knowledge.
- [ ] **Verify api/worker images by digest** for the same reason. Set
  `image.tag` to an immutable version, and prefer overriding to the
  `@sha256:…` form in your environment overlay.
- [ ] **Verify cosign signatures** on every release image. The `release.yml`
  workflow signs each image keylessly via Fulcio/Rekor:

  ```bash
  cosign verify \
    --certificate-identity-regexp "https://github.com/.*/document-viewer" \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    ghcr.io/jhested/document-viewer-api@sha256:…
  ```

  Wire this into your admission controller (Sigstore policy-controller,
  Kyverno) so unsigned or tampered images cannot run.
- [ ] **Scan images with Trivy** (or equivalent) on every deploy. Fail the
  pipeline on HIGH/CRITICAL CVEs in the runtime path.
- [ ] **CodeQL is already configured** (`.github/workflows/codeql.yml`) and runs
  on every push, every PR to `main`, and weekly. Keep the workflow enabled and
  triage findings.
- [ ] **Consume the SBOM.** The release workflow generates a `syft` SBOM and
  attaches it as a build artefact. Feed it into your continuous vulnerability
  monitoring (Dependency-Track, Snyk, GitHub's Dependabot security advisories).

## Runtime posture (already enforced by the chart)

The Helm templates enforce these for `api`, `worker`, and `gotenberg`. Do not
remove them in a downstream values override.

- `runAsNonRoot: true`
- `readOnlyRootFilesystem: true`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: [ALL]`
- Memory tmpfs at `/tmp` for Gotenberg
- Resource requests and limits set

Verify with:

```bash
kubectl -n viewer get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].securityContext}{"\n"}{end}'
```

## Secrets

- [ ] **Store JWT secrets in a secret manager** (Vault, AWS Secrets Manager,
  GCP Secret Manager, Sealed Secrets, External Secrets Operator) — not in the
  Helm values file checked into Git.
- [ ] **Rotate S3 access keys quarterly.** Use IAM roles for service accounts
  (IRSA) on EKS or workload identity on GKE/AKS where available, so no
  long-lived keys exist.
- [ ] **S3 credentials must be read-only.** The worker only needs `s3:GetObject`
  (and optionally `s3:HeadObject`) on the bucket prefix. No `PutObject`, no
  `DeleteObject`, no `ListBucket` outside what's required.
- [ ] **Redis password** (`requirepass`) and TLS in production deployments.

## Audit logging

- [ ] **Ship structured JSON logs to a SIEM** (Splunk, Elastic, Loki + Grafana,
  Datadog). Events emitted: `page_rendered`, `manifest_returned`, `job_failed`,
  `token_rejected`, `token_replayed`, `mime_rejected`, `size_exceeded`.
- [ ] **Retain audit logs for 90+ days.** KYC/AML regulations typically require
  much longer retention for case-bound records; align with your compliance
  team. Minimum 90 days for operational forensics.
- [ ] **Alert on `token_replayed` and `mime_rejected` spikes.** These are
  indicators of either an integration bug or active probing.
- [ ] **Cross-reference `request_id`** in every error response and log line.

## Ingress logs

- [ ] **Redact the JWT from access logs.** Tokens travel in the URL path. The
  default access-log format of most ingress controllers will capture them.
  Either:
  - Drop the URL path entirely from access logs, or
  - Use a log format that omits the query string and tokenised path segment,
    or
  - Set short retention (hours, not days) on raw access logs and post-process
    them into redacted forms for long-term storage.

## Operational maintenance

- [ ] **Quarterly key rotation drill.** Practise rotating the JWT signing
  material end-to-end with the back-office team. The first time should not be
  during an incident.
- [ ] **Re-pin Gotenberg, PDFium, and Pillow versions** whenever a security
  advisory affects them. The parser surface is the largest part of our attack
  surface that we don't own.
- [ ] **Restart Gotenberg daily** via a Kubernetes `CronJob` (or
  `docker compose restart gotenberg` on Compose deployments). LibreOffice
  recycles processes per request, but a 24-hour restart sweeps any accumulated
  state from `/tmp` (which is tmpfs, but still).
- [ ] **Review the security regression corpus** (`tests/security-corpus/`)
  whenever the cleaner, the renderer, or the mime detector changes.

## Pre-deploy verification

Run this checklist immediately before a production deploy:

```text
[ ] gotenberg image is pinned by digest, not tag
[ ] api and worker images are pinned by digest, not tag
[ ] cosign verification passes against the digests in use
[ ] Trivy scan has no HIGH/CRITICAL findings
[ ] JWT_REQUIRED_ISS is set
[ ] JWT secrets live in a secret manager
[ ] S3 credentials are read-only
[ ] Default-deny NetworkPolicy exists in the viewer namespace
[ ] Redis is on a private network with auth
[ ] Ingress redacts the URL path from access logs
[ ] SIEM is receiving the seven audit events
[ ] Alert rules for token_replayed and mime_rejected are armed
```
