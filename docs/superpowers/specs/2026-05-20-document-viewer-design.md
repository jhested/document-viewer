# Document Viewer — Design Spec

**Status:** Approved (brainstorming)
**Date:** 2026-05-20
**Owner:** Jimmi Hested

## 1. Purpose

A Docker-deployed render service that safely transforms KYC/AML source files (PDF, office documents, images) into watermarked page images, served as a stateless HTTP API. Two design goals:

- **A. Safe rendering of potentially malicious files.** Source bytes are parsed and rendered in isolated worker containers; the rendered output (images only) is what reaches consumer browsers.
- **B. Protect PII from spreading.** Originals never leave the server. Output is per-user, watermarked, short-TTL cached, never offered as a download.

The service is a **renderer, not a viewer app.** It exposes an image API; callers (back-office tools) embed images directly. An optional tiny embed shell is shipped for testing and as a reference integration.

## 2. Out of scope (v1)

- File upload by employees (source is always object storage)
- Editing, annotation, redaction
- OCR / text extraction
- A full file-browser UI
- Authoring/registering documents
- Downloadable original files — there is no privileged escape hatch
- Multi-tenant configuration (single deployment serves one logical tenant)

## 3. High-level architecture

```
                 ┌──────────────────────────┐
   ingress ────► │  viewer-api  (FastAPI)   │ ── verifies JWT, replay-protects
   (nginx /      │  - auth, routing         │ ── cache lookup
    traefik)     │  - serves rendered pages │ ── enqueues render jobs
                 │  - serves embed shell    │ ── streams pages back
                 └────────┬──────────┬──────┘
                          │          │
                       Redis     ┌───┴──────────────────────┐
                  (queue+cache)  │  viewer-worker (Python)  │ ── pulls source from S3
                                 │  - mime detect           │ ── PDF→images (PyMuPDF)
                                 │  - PDF/image pipeline    │ ── image re-encode (Pillow)
                                 │  - cache writes          │ ── watermarks
                                 └────────┬─────────────────┘
                                          │ HTTP multipart
                                          │ (only for office formats)
                                ┌─────────┴────────────────────┐
                                │ gotenberg  (upstream image)  │ ── gotenberg/gotenberg:8
                                │ - office → PDF via           │ ── /forms/libreoffice/convert
                                │   LibreOffice (internal pool)│ ── stateless HTTP
                                │ - hardened by orchestrator:  │ ── no shared volume needed
                                │   no egress, ro fs, no caps  │
                                └──────────────────────────────┘
```

**Containers:**

| Container | Image | Purpose | Network egress | Secrets |
|---|---|---|---|---|
| `viewer-api` | ours | HTTP surface, JWT verify, cache lookup, embed shell | Redis only | JWT verify key, Redis URL |
| `viewer-worker` | ours | Render pipeline, S3 fetch, Gotenberg client | Redis, S3/MinIO, Gotenberg | S3 read creds, Redis URL |
| `gotenberg` | `gotenberg/gotenberg:8` (pinned by digest) | Office → PDF only | **none (orchestrator-enforced)** | none |
| `redis` | upstream | Job queue + page cache | internal | – |

Gotenberg is only invoked when a job's detected mime is an office format. It stays running but idle otherwise. The worker calls `POST {GOTENBERG_URL}/forms/libreoffice/convert` with the source file as multipart form data and reads the PDF response body.

**Gotenberg hardening (orchestrator-enforced):**
- **Compose:** `read_only: true`, `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, on an internal-only Docker network with no internet route. CPU + memory limits.
- **K8s:** `securityContext` with `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`. A `NetworkPolicy` allows ingress only from `viewer-worker` pods and **denies all egress** (no internet, no cluster-internal lateral movement). Resource requests/limits set.
- Pinned by image digest, not `:8` tag, so updates are intentional.

## 4. API surface

All paths require a JWT (see §6). Token is in the URL path so it can be embedded as an `<img src>` directly.

### `GET /render/{jwt}/manifest`
Returns rendering metadata.

Response 200 (also served with `Cache-Control: no-store`):
```json
{
  "mime": "application/pdf",
  "pages": 12,
  "dims": [{"w": 1700, "h": 2200}, ...],
  "etag": "sha256:...",
  "ttl_seconds": 900
}
```

For office formats, this call triggers the LibreOffice conversion (cached for the duration of the TTL) so page counts are accurate. Subsequent page requests reuse the intermediate PDF.

### `GET /render/{jwt}/page/{n}?w={width}`
Returns a single rendered page as WebP.

- `n` is 1-indexed.
- `w` is the requested width in pixels. Server caps at `MAX_PAGE_WIDTH` env (default 2400). Server picks DPI accordingly.
- Response: `image/webp` body, `Cache-Control: no-store`. (No browser cache, no shared cache — each render is per-user watermarked PII.)

### `GET /embed/{jwt}`
Returns a static HTML+JS page (single file, vanilla JS, no CDN deps) that:
- Calls `/manifest` for the same JWT
- Renders each page as `<img>` with lazy scroll loading
- Provides zoom controls (re-requests with different `w`)
- Shows page X of Y

Used for testing and as a reference integration. Callers can build their own UI on the API without it.

### `GET /healthz`, `GET /readyz`
Liveness/readiness probes. `readyz` checks Redis connectivity and at least one worker heartbeat in the last 30s.

### Errors

| Status | Meaning |
|---|---|
| 401 | JWT invalid, expired, or replayed |
| 404 | Object not found in source backend |
| 415 | Detected mime type not in allowlist |
| 504 | Render exceeded per-page timeout |
| 503 | All workers busy and queue full |
| 500 | Render failed (worker crashed, OOM, etc) — returned with `X-Request-ID` for audit lookup |

Error bodies are intentionally sparse: `{"error": "...", "request_id": "..."}`. No source-bytes-derived detail in errors.

## 5. Rendering pipelines

| Source mime | Pipeline |
|---|---|
| `application/pdf` | PyMuPDF opens stream → render page N to RGB at DPI = `clamp(w / page_pt_width * 72, 72, 300)` → Pillow watermark → encode WebP (q=82, method=4) → cache |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (.docx) | Worker POSTs source as multipart to `{GOTENBERG_URL}/forms/libreoffice/convert` with a per-request timeout → receives PDF response → PDF goes through the PDF pipeline above. Intermediate PDF cached per-JWT for the manifest TTL. |
| `.pptx`, `.xlsx`, `.odt`, `.ods`, `.odp`, `.rtf` | Same as docx — all handled by Gotenberg's LibreOffice route |
| `image/png`, `image/jpeg`, `image/webp` | Pillow opens → strip all EXIF/metadata → re-encode WebP → watermark → cache. Single page. |
| `image/heic` | Same, via `pillow-heif` plugin |
| `image/tiff` | Multi-page: each page → re-encode WebP → watermark → cache |
| `image/gif` | First frame only, treated as still |

**Mime detection** uses `python-magic` against the first 4KB of the streamed source. Extension is ignored. If detected mime is not in the allowlist, return 415 *before* any further parsing.

**Size caps** (all env-configurable):
- `MAX_SOURCE_BYTES` (default 100 MB)
- `MAX_PAGES` (default 500)
- `MAX_PAGE_WIDTH` (default 2400)
- `RENDER_TIMEOUT_SECONDS` per page (default 30)
- `OFFICE_TIMEOUT_SECONDS` per conversion (default 60)

Exceeding any cap returns a clean error; the worker is unaffected.

## 6. Authentication

Stateless JWT issued by the upstream back-office app, verified by `viewer-api`.

**Claims:**
```json
{
  "iss": "back-office",
  "sub": "alice@bank.com",
  "obj": "kyc/case-123/passport.pdf",
  "case": "case-123",
  "iat": 1716200000,
  "exp": 1716200600,
  "jti": "<uuid>"
}
```

**Algorithm:** RS256 (back-office signs with private key; viewer verifies with public key). HS256 supported as a config alternative for simpler deployments.

**Replay protection:** `viewer-api` records `jti` in Redis via `SETNX` with TTL = `exp - iat`. Reuse → 401.

**Token in URL:** Acceptable here because tokens are short-lived (5–15 min recommended), single-use, and scoped to a single object + user. URL ends up in ingress logs — operators should either drop the path in log format or rotate logs aggressively.

**Ingress pre-validation (optional):** Operators may put an ingress-level JWT validator (oauth2-proxy, Traefik plugin, k8s ingress filter, nginx `auth_jwt` module) in front of `viewer-api` to drop bad tokens at the edge. `viewer-api` always validates again — defense in depth, and the API still needs the claims to know what to render. The viewer never trusts upstream-injected user headers in place of the JWT.

**Watermark inputs** are taken from claims: `sub`, `case`, and the rendering server's current ISO timestamp.

## 7. Source abstraction

```python
class SourceBackend(Protocol):
    async def fetch(self, key: str) -> tuple[AsyncIterator[bytes], str]:
        """Returns (byte stream, etag)."""

    async def head(self, key: str) -> str:
        """Returns etag, or raises NotFound."""
```

**Implementations:**
- `S3Backend` (default): `aioboto3`, endpoint URL configurable for MinIO/Ceph.
- `FilesystemBackend`: rooted at a config path, for dev and tests.

Backend selected via `SOURCE_BACKEND=s3|fs` env var. Adding Azure Blob / GCS later is one new class + config — no other code changes.

## 8. Caching

- **Storage:** Redis with `CONFIG SET maxmemory-policy allkeys-lru`.
- **Key:** `page:{sha256(etag || sub || n || w)}`
- **Value:** WebP bytes.
- **TTL:** `CACHE_TTL_SECONDS` env, default 900 (15 min).
- **Intermediate office PDFs:** `office:{sha256(etag || jti)}` → PDF bytes, same TTL.

ETag-keyed: if the source object changes in MinIO/Ceph, cache misses automatically and we re-render from new content.

Per-user keying because the watermark is baked into the image — different watermark = different cache entry. Acceptable size cost given short TTL.

## 9. Watermarking

- Diagonal semi-transparent text, `<sub> · <case> · <ISO timestamp>`.
- Rendered into the WebP itself (PIL `ImageDraw` over RGBA composite), not as a CSS/DOM overlay.
- Configurable: opacity (default 0.18), font size (default 24pt), rotation angle (default -30°), color (default `#808080`).
- Same string rendered at multiple positions on each page (tiled), so cropping out one instance leaves others.

## 10. Isolation specifics

**`gotenberg` container hardening** (the highest-risk surface — runs LibreOffice on untrusted office files):
- **Compose:** `read_only: true`; `tmpfs: { /tmp: rw,noexec,nosuid,size=512m }`; `cap_drop: [ALL]`; `security_opt: [no-new-privileges:true]`; attached to an internal-only Docker network with no internet route; memory limit 1.5g; cpus 1.5; `restart: unless-stopped`.
- **K8s:** `securityContext: { runAsNonRoot: true, runAsUser: 1001, readOnlyRootFilesystem: true, allowPrivilegeEscalation: false, capabilities: { drop: [ALL] } }`; `emptyDir` (memory-medium) at `/tmp`; `NetworkPolicy` denying all egress and allowing ingress only from `viewer-worker` pods; resource requests + limits; pinned image digest.
- **Periodic restart:** k8s `CronJob` (or compose `restart` policy + periodic `docker compose restart gotenberg`) every 24h to flush any accumulated state. Gotenberg internally recycles LibreOffice processes per request, so per-job recycling is already handled.

**`viewer-worker`** has S3 read-only credentials. Runs untrusted parsers (PyMuPDF, Pillow); each render runs in a subprocess with a hard timeout. Pillow opened with `MAX_IMAGE_PIXELS` set to prevent decompression bombs. Has network access to Redis, S3/MinIO, and Gotenberg only — enforced by `NetworkPolicy` on k8s, by network membership on Compose.

**`viewer-api`** runs no parsers; it only verifies JWTs and serves bytes from Redis. Network access to Redis only.

**Inter-container communication** (worker ↔ gotenberg): HTTP multipart over an internal network. No shared filesystem. Worker streams the source file in the request body; Gotenberg returns the PDF in the response body. Both sides bounded by request timeout.

## 11. Error handling principles

- **Fail closed.** Any rendering error returns an error response, never the original bytes.
- **Worker crashes are not fatal to the system.** Job marked failed, container restarted, queue continues. Other in-flight jobs survive.
- **Gotenberg crashes** are handled by orchestrator restart policy; in-flight jobs in our worker fail cleanly with a 500 + request ID, and the next request reaches a fresh Gotenberg pod/container.
- **No source-bytes-derived detail in errors** — error messages reference our mime allowlist and size caps, not the file's actual content.
- **Request IDs** in every error response and log line for audit cross-reference.

## 12. Audit logging (v1)

Structured JSON to stdout, one event per page render:

```json
{
  "ts": "2026-05-20T14:30:12.481Z",
  "request_id": "uuid",
  "event": "page_rendered",
  "sub": "alice@bank.com",
  "case": "case-123",
  "obj_sha": "sha256:...",
  "mime": "application/pdf",
  "page": 3,
  "width": 1200,
  "render_ms": 145,
  "cache_hit": false,
  "ip": "10.x.x.x",
  "user_agent": "..."
}
```

Events: `page_rendered`, `manifest_returned`, `job_failed`, `token_rejected`, `token_replayed`, `mime_rejected`, `size_exceeded`. Ship to Loki/ELK via standard container log scraping.

## 13. Configuration

Single `.env.example` documenting every variable. Categories:

- **Auth:** `JWT_ALGORITHM`, `JWT_PUBLIC_KEY`, `JWT_HMAC_SECRET`, `JWT_REQUIRED_ISS`
- **Source:** `SOURCE_BACKEND`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `FS_ROOT`
- **Limits:** `MAX_SOURCE_BYTES`, `MAX_PAGES`, `MAX_PAGE_WIDTH`, `RENDER_TIMEOUT_SECONDS`, `OFFICE_TIMEOUT_SECONDS`
- **Cache:** `REDIS_URL`, `CACHE_TTL_SECONDS`
- **Worker:** `WORKER_CONCURRENCY`, `GOTENBERG_URL`
- **Watermark:** `WATERMARK_OPACITY`, `WATERMARK_FONT_SIZE`, `WATERMARK_ANGLE`, `WATERMARK_COLOR`
- **Mime allowlist:** `ALLOWED_MIMES` (comma-separated)

Sensible defaults in the app so a minimal `.env` with only auth + source creds boots.

## 14. Testing strategy (TDD)

Implementation must follow **red-green-refactor**: failing test first, minimum code to pass, refactor.

**Unit tests** (fast, no I/O):
- Mime detection from byte streams (including spoofed extensions)
- JWT verify/replay logic (valid, expired, wrong sig, missing claims, replayed jti)
- Source abstraction contract (both backends pass the same suite)
- Cache key derivation (deterministic, includes all sensitive inputs)
- Watermark rendering (positions, opacity bounds)
- Size cap enforcement (each cap triggers its own clean error)

**Integration tests** (compose-test profile):
- Spin up MinIO + Redis + Gotenberg + `viewer-api` + `viewer-worker`
- Upload fixture files (PDFs, DOCX, XLSX, PNG, TIFF, malformed corpus) to MinIO
- Issue JWTs with a test signing key
- Assert: manifest matches expected, page renders to a non-empty WebP, second request hits cache, expired JWT 401s, replay 401s, office formats round-trip through Gotenberg, Gotenberg's `:3000` is unreachable from outside the worker

**Security regression corpus** (committed to repo, ~30 files):
- Malformed PDFs (truncated, oversized streams, embedded JS, embedded files)
- DOCX with macros, OLE objects, external image refs
- Zip bombs (DOCX is a zip; test the dezipper limits)
- Image decompression bombs (pixel-flood, malformed headers)
- Wrong-extension files (.pdf that's actually a PE, etc — must be rejected via magic)

For each, the test asserts: either renders safely, or returns a clean documented error. No worker permanent crash, no source bytes in the response.

**Property tests** for the renderer:
- Any JPEG/PNG smaller than the cap renders without error
- Output dimensions match request `w` within ±1 pixel
- Watermark text always present in output (OCR check against the rendered image)

**Load smoke test** (not a CI gate, manual): 50 concurrent PDFs at 10 pages each — assert no OOMs, p95 page render < 2s on the target host.

## 15. Open implementation choices (deferred to the plan)

These are decisions the implementation plan needs to make, but they don't affect the architecture:

- Queue library: `arq` vs custom asyncio loop vs `dramatiq`
- WebP encoder params (q, method) tuned via benchmark
- Exact font shipped for watermarking (Inter / DejaVu Sans)
- Whether the embed shell should support pinch-to-zoom on mobile in v1

## 16. Deliverables

- `document-viewer/` directory containing:
  - `services/api/` — FastAPI app (also serves the embed shell as a static asset)
  - `services/worker/` — render pipelines + Gotenberg client
  - `services/embed/` — static HTML+JS shell, bundled into the api image
  - `Dockerfile` per service (api, worker) — Gotenberg is pulled from upstream by digest
  - **Local dev / single-host:**
    - `compose.yaml` (Compose v2, podman-compose compatible) — prod-shaped deployment
    - `compose.test.yaml` — integration test stack (MinIO + Redis + Gotenberg + api + worker)
  - **Kubernetes:**
    - `helm/document-viewer/` chart with:
      - `Chart.yaml`, `values.yaml`, `values.example.yaml`
      - `Deployment` per service (api, worker, gotenberg, redis if not external)
      - `Service` + `Ingress` for api
      - `NetworkPolicy` denying gotenberg egress, restricting worker→gotenberg ingress
      - `SecurityContext` blocks per pod
      - `ConfigMap` and `Secret` templates
      - `HorizontalPodAutoscaler` for worker (optional, behind a values flag)
      - `ServiceMonitor` (optional) for Prometheus scraping
  - `.env.example`
  - `README.md` — quick start (both compose and helm), integration guide, threat model summary
  - `tests/` — unit, integration, security corpus
  - `docs/superpowers/specs/` — this design
