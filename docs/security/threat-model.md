# Threat model

This document is an honest, STRIDE-flavoured statement of what `document-viewer`
defends against and what it does not. The companion file
[`known-limitations.md`](known-limitations.md) is required reading — it covers
the residual risks an operator must own with policy and process.

`document-viewer` is a render service for KYC/AML workflows. Two design goals
frame the entire threat model:

1. **Isolate untrusted file parsing.** Source documents (PDF, office, image)
   are assumed hostile.
2. **Prevent original-byte leakage.** Originals stay on the backing store; only
   per-user, watermarked, short-TTL page rasters are served downstream.

Everything below should be read against those two goals.

## Trust boundaries

```text
back-office (signs JWT) ──► ingress ──► viewer-api ──► viewer-worker ──► gotenberg
                                            │             │                 │
                                          redis         s3/minio       libreoffice
```

| Boundary | Crossing | Defence |
|---|---|---|
| Internet → ingress | TLS-terminated HTTP request | Operator-supplied ingress (out of scope for this repo) |
| Ingress → `viewer-api` | HTTP + JWT in URL | `JwtVerifier` re-validates signature, expiry, issuer, required claims |
| `viewer-api` → Redis | TCP | Network policy + Redis on private network |
| `viewer-worker` → S3 | TCP/TLS | Read-only IAM credentials |
| `viewer-worker` → Gotenberg | HTTP multipart | NetworkPolicy: only the worker can reach Gotenberg |
| `viewer-worker` ↔ untrusted bytes | In-process parsing | Subprocess timeout, Pillow `MAX_IMAGE_PIXELS`, pikepdf pre-clean |
| Gotenberg → internet | none | NetworkPolicy denies all egress from Gotenberg |

## Threats defended

The table below uses STRIDE categories loosely; the rightmost column points at
the specific code or configuration that implements the control.

| # | Threat | STRIDE | Defence | Where |
|---|---|---|---|---|
| 1 | Malicious PDF embeds JavaScript, OpenAction, AA, Launch, GoToR, ImportData, SubmitForm, or attachments and tries to execute on render | Tampering / Elevation | `pikepdf` strips `/JavaScript`, `/JS`, `/OpenAction`, `/AA`, `/AcroForm`, `/Names` (with `/EmbeddedFiles`, `/JavaScript`), per-page `/AA`, and annotation-level `/A`, `/AA`, `/JS` **before** `pypdfium2` ever opens the file | `src/document_viewer/render/pdf_clean.py` |
| 2 | Encrypted PDF used to confuse the renderer or smuggle content past inspection | Tampering | `pikepdf.open` raises `PasswordError`; cleaner re-raises as `RuntimeError("pdf is encrypted; refusing to render")` — request fails closed | `pdf_clean.py:18` |
| 3 | Decompression bomb (image with absurd pixel count) | DoS | `Pillow.Image.MAX_IMAGE_PIXELS` is set on import; oversized images raise before allocation | `services/worker` Pillow init |
| 4 | Zip bomb inside DOCX/XLSX | DoS | Office files go through Gotenberg/LibreOffice in an isolated, resource-capped pod with `NetworkPolicy` denying all egress; the worker enforces a hard request timeout and source-size cap before forwarding | `OFFICE_TIMEOUT_SECONDS`, `MAX_SOURCE_BYTES`, gotenberg deployment + networkpolicy |
| 5 | Spoofed file extension (`.pdf` that is actually a PE binary, etc.) | Tampering | `python-magic` magic-byte detection against a strict mime allowlist; extension is never trusted | `src/document_viewer/shared/mime.py` |
| 6 | LibreOffice (inside Gotenberg) is exploited and the attacker tries to call out | Elevation / Exfiltration | Gotenberg pod runs `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`; NetworkPolicy ingress only from `viewer-worker`, **egress `[]` (default-deny)**; tmpfs `/tmp` only | `helm/document-viewer/templates/gotenberg-{deployment,networkpolicy}.yaml` |
| 7 | Original-byte PII exfiltration through the API | Information disclosure | The API serves only rasterized WebP pages; original bytes are read by the worker from S3 and never propagate downstream. No download endpoint exists | API surface in `services/api` |
| 8 | EXIF / XMP / IPTC metadata leak through rendered images | Information disclosure | Image pipeline opens with Pillow, strips all metadata, and re-encodes to WebP before watermarking | `services/worker` image pipeline |
| 9 | Token replay (URL captured from ingress log, browser history, screen-share) | Spoofing | `JwtReplayGuard` records `jti` in Redis via `SET … NX EX <remaining>`; second use raises `TokenReplayed` → 401 | `src/document_viewer/shared/jwt_auth.py:85` |
| 10 | Forged or tampered JWT | Spoofing | `JwtVerifier` enforces algorithm (RS256/HS256), signature, issuer, and required claims (`iss`, `sub`, `obj`, `case`, `jti`, `iat`, `exp`) | `src/document_viewer/shared/jwt_auth.py:38` |
| 11 | Expired JWT replayed | Spoofing | PyJWT `ExpiredSignatureError` → `TokenExpired` → 401 | `src/document_viewer/shared/jwt_auth.py:69` |
| 12 | Ingress misconfigured to bypass auth (ingress-level JWT validator removed or misrouted) | Spoofing | The API itself always verifies the token. Defense in depth: even with no ingress filter, the API rejects bad tokens | `JwtVerifier.verify` in `viewer-api` |
| 13 | Upstream-injected user header trying to impersonate a subject | Spoofing | The API never trusts request headers for identity; the watermark, cache key, and audit log read `sub`/`case` from the verified JWT only | API request handling |
| 14 | Path traversal on the filesystem source backend (`../../etc/passwd`) | Tampering | `FilesystemBackend._resolve` resolves the path and calls `Path.relative_to(root)`; mismatch raises `ObjectNotFound` (404) | `src/document_viewer/shared/source.py:26` |
| 15 | Worker exfiltrates raw bytes via stack trace in an error response | Information disclosure | Errors are mapped to a fixed taxonomy (mime/size/timeout/internal); message bodies never echo source bytes | `services/api` error handlers |
| 16 | Persisted state between rendering jobs in Gotenberg (e.g. cached LibreOffice user profile) | Information disclosure | tmpfs `/tmp` on `emptyDir(medium: Memory)`, readOnlyRootFilesystem, and a daily CronJob restart of Gotenberg flush accumulated state | gotenberg deployment, operator cronjob |
| 17 | Cache poisoning across users (one user receiving another user's watermarked page) | Information disclosure | Cache key includes `sub`, `etag`, `n`, `w` — per-user keying. Different watermarks → different cache entries | `src/document_viewer/shared/cache_keys.py` |
| 18 | Stale page after the source object is replaced in S3 | Tampering | Cache key includes the object's ETag; replacing the object invalidates the cache automatically | same |
| 19 | Worker is compromised and tries to write back to S3 | Tampering | S3 credentials are read-only by deployment convention; the chart documents this in `values.example.yaml` | `helm/document-viewer/values.example.yaml`, operator IAM |
| 20 | Container privilege escalation (runtime, kernel exploit) | Elevation | All three workloads run `runAsNonRoot`, `readOnlyRootFilesystem`, drop all capabilities | `helm/document-viewer/templates/{api,worker,gotenberg}-deployment.yaml` |

## Threats not defended

These are explicit non-goals. The system does not protect against them and an
operator must address them with policy, hardware, or process — not with this
service.

| # | Threat | Why not defended | Mitigation lives elsewhere |
|---|---|---|---|
| N1 | Screenshot, screen recording, copy-of-the-monitor with a phone | Any rendered page exists as pixels in the user's browser. There is no DRM. By design | Endpoint policy (MDM, screen-record disable), camera policy |
| N2 | OS-level exfiltration by a user with admin on their workstation | Once pixels reach an authorised user's machine, they're outside our trust boundary | Endpoint management, principle-of-least-privilege on workstations |
| N3 | Coerced or malicious employee with legitimate access exfiltrating to a personal channel | The employee is authorised — the system *correctly* renders the page for them | UEBA, DLP at the network egress, audit log review, separation of duties |
| N4 | Real-time DLP scan of document content for SSNs, IBANs, etc. | Out of scope. The service renders; it does not classify | A DLP appliance between the user's browser and the wider internet |
| N5 | Supply-chain compromise of Gotenberg, PDFium, Pillow, libmagic, or pikepdf | We pin and patch but cannot detect a malicious upstream release on day zero | Image digest pins, Trivy + CodeQL scans, prompt re-pinning when CVEs land |
| N6 | Resource-exhaustion DoS beyond rate-limits and size caps (sustained volume from many valid tokens) | Rate limits and size caps protect against single-actor floods; volumetric DoS from a botnet with valid tokens is a fleet-capacity problem | Ingress rate-limit, WAF, HPA tuning, capacity planning |
| N7 | Side-channel attacks (timing, CPU cache) inferring source-object identity from response timings | Not modelled. Render times correlate with page complexity | Not addressed |
| N8 | Compromise of the back-office signing key | Once an attacker can sign JWTs, they can request anything the back-office can. The viewer trusts the signature | Key rotation, HSM-backed signing, SIEM on issuance |
| N9 | Malicious operator of the `viewer-api`, `viewer-worker`, or Kubernetes cluster | The cluster operator is inside the trust boundary | Cluster RBAC, audit, separation of duties between back-office and viewer ops |
| N10 | Anti-tampering on the watermark | Watermark is tiled, so a single crop leaves others — but a determined attacker with image-editing tools can manually remove it from each tile | Treat the watermark as a deterrent and audit trail, not a hard control |

## Token-in-URL: known trade-off

The render token travels in the URL. We accept this because:

- Tokens are short-lived (5–15 min recommended).
- Each `jti` is single-use (replay-guarded).
- Tokens are scoped to one `obj` + one `sub`.

The URL still ends up in ingress access logs. Operators must either redact the
path from access-log format, rotate logs aggressively, or store them with
appropriate retention and access controls. See
[`hardening.md`](hardening.md#ingress-logs).

## Re-evaluation triggers

Re-read this document when any of the following change:

- A new source MIME type is added to the allowlist.
- The PDF cleaning pipeline (`pdf_clean.py`) is modified.
- The JWT scheme or claim set changes.
- Cache keying changes.
- A new source backend lands.
- A new container is added to the deployment.
