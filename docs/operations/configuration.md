# Configuration

All runtime configuration is loaded from environment variables by
`document_viewer.shared.config.Settings` (pydantic-settings). Settings are read
once at process start; changing a value requires a restart of the API and worker
pods that read it.

For a working starter file see `.env.example` at the repository root. Copy it to
`.env` for local Compose, or translate the values into the chart's `config:` and
`secrets:` sections for Helm.

## Required variables

The following must be set for the application to start.

| Name | Default | Allowed values | What it controls |
|---|---|---|---|
| `REDIS_URL` | _none_ | `redis://host:port/db` URL | Connection string for Redis. Used for the JWT replay guard (SETNX with TTL), the page-image cache, and the arq job queue. |
| `SOURCE_BACKEND` | _none_ | `s3` or `fs` | Which `SourceBackend` implementation to instantiate. `s3` reads via aioboto3; `fs` reads from a local path (development/testing). |

## Auth

| Name | Default | Allowed values | What it controls |
|---|---|---|---|
| `JWT_ALGORITHM` | `RS256` | `HS256`, `RS256` | Signing algorithm the API will accept for embed tokens. `RS256` (asymmetric, public-key verification) is the production choice; `HS256` is only intended for tests and local development. |
| `JWT_HMAC_SECRET` | empty string | any string | Shared secret used when `JWT_ALGORITHM=HS256`. Must be at least 32 bytes of entropy. Ignored under `RS256`. |
| `JWT_PUBLIC_KEY` | empty string | PEM-encoded public key | Public key used to verify tokens when `JWT_ALGORITHM=RS256`. The matching private key lives in the upstream issuer (the back-office). |
| `JWT_REQUIRED_ISS` | _none_ (no check) | any string | If set, tokens whose `iss` claim does not match are rejected. Pin this to the back-office service name to defend against cross-system token reuse. |

## Source backend

Only the variables that match `SOURCE_BACKEND` need to be set.

| Name | Default | Allowed values | What it controls |
|---|---|---|---|
| `S3_ENDPOINT` | _unset_ | URL | S3 endpoint URL. Required when `SOURCE_BACKEND=s3`. Set to your provider endpoint (AWS) or MinIO/Ceph URL for self-hosted. |
| `S3_BUCKET` | _unset_ | bucket name | Bucket the viewer reads source documents from. Required when `SOURCE_BACKEND=s3`. |
| `S3_REGION` | `us-east-1` | AWS region code | Region passed to the S3 client. |
| `S3_ACCESS_KEY_ID` | _unset_ | string | Access key for the S3 client. Required when `SOURCE_BACKEND=s3`. |
| `S3_SECRET_ACCESS_KEY` | _unset_ | string | Secret key for the S3 client. Required when `SOURCE_BACKEND=s3`. |
| `FS_ROOT` | `/tmp/docs` | absolute path | Root directory the filesystem backend resolves source keys against. Required when `SOURCE_BACKEND=fs`. The default is a dev placeholder; production filesystem deployments must override it. The backend has a traversal guard that rejects paths escaping the root. |

## Worker

| Name | Default | Allowed values | What it controls |
|---|---|---|---|
| `GOTENBERG_URL` | `http://gotenberg:3000` | URL | Internal URL the worker uses to reach the Gotenberg sidecar for office-to-PDF conversion. In Helm, the chart wires this to the in-namespace Gotenberg service automatically. |
| `WORKER_CONCURRENCY` | `4` | positive integer | Maximum number of concurrent render jobs a single worker process will execute (passed to arq as `max_jobs`). Render work is CPU-bound: see [tuning.md](tuning.md). |

## Limits

These caps protect the worker from pathological inputs. Tighten them in
high-throughput deployments; loosen them only after confirming worker pods have
the headroom (see [tuning.md](tuning.md)).

| Name | Default | Allowed values | What it controls |
|---|---|---|---|
| `MAX_SOURCE_BYTES` | `104857600` (100 MiB) | positive integer (bytes) | Maximum source document size accepted by the pipeline. Sources larger than this are rejected before any parsing happens. |
| `MAX_PAGES` | `500` | positive integer | Maximum page count per source. PDFs with more pages are rejected during manifest generation. |
| `MAX_PAGE_WIDTH` | `2400` | positive integer (pixels) | Hard cap on the rendered image width in pixels. Width requested by the client is clamped to this value in `RenderPipeline.render_page`. |
| `RENDER_TIMEOUT_SECONDS` | `30` | positive integer | Per-page render timeout. Pages that exceed this time are aborted. |
| `OFFICE_TIMEOUT_SECONDS` | `60` | positive integer | Office-to-PDF (Gotenberg) conversion timeout. The longer ceiling reflects that LibreOffice conversion is typically slower than native PDF rendering. |

## Cache

| Name | Default | Allowed values | What it controls |
|---|---|---|---|
| `CACHE_TTL_SECONDS` | `900` (15 min) | positive integer | TTL for cached page images and cleaned-PDF artifacts in Redis. Shorter TTLs reduce Redis memory at the cost of more re-rendering; longer TTLs raise hit ratio but require more Redis memory. See [tuning.md](tuning.md). |

## Watermark

The watermark is rendered into every page image. These knobs affect the visible
appearance only; they are not security controls.

| Name | Default | Allowed values | What it controls |
|---|---|---|---|
| `WATERMARK_OPACITY` | `0.18` | float in `[0.0, 1.0]` | Per-tile opacity of the watermark overlay. |
| `WATERMARK_FONT_SIZE` | `24` | positive integer | Font size in points used for the watermark text. |
| `WATERMARK_ANGLE` | `-30.0` | float (degrees) | Rotation angle of the tiled watermark. |
| `WATERMARK_COLOR` | `#808080` | CSS hex color `#RRGGBB` | Watermark fill color. |

## Allowlist

| Name | Default | Allowed values | What it controls |
|---|---|---|---|
| `ALLOWED_MIMES` | see below | JSON list of strings | Allowlist of MIME types that may enter the render pipeline. Detection uses magic bytes (libmagic), not file extensions. Sources outside the allowlist are rejected with `415 Unsupported Media Type` before any parser touches them. |

Default `ALLOWED_MIMES`:

```text
application/pdf
application/vnd.openxmlformats-officedocument.wordprocessingml.document
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
application/vnd.openxmlformats-officedocument.presentationml.presentation
application/vnd.oasis.opendocument.text
application/vnd.oasis.opendocument.spreadsheet
application/vnd.oasis.opendocument.presentation
application/rtf
image/png
image/jpeg
image/webp
image/heic
image/tiff
image/gif
```

To restrict to PDFs only, set:

```bash
ALLOWED_MIMES='["application/pdf"]'
```

## Where each variable is consumed

- `JWT_*`, `REDIS_URL`: API process (`document_viewer.api`).
- `SOURCE_BACKEND`, `S3_*`, `FS_ROOT`: worker process. The API never opens a source.
- `GOTENBERG_URL`, `WORKER_CONCURRENCY`, `RENDER_TIMEOUT_SECONDS`, `OFFICE_TIMEOUT_SECONDS`, `MAX_*`, `ALLOWED_MIMES`, `WATERMARK_*`: worker process.
- `CACHE_TTL_SECONDS`: shared by API (cache reads) and worker (cache writes).
