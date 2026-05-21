# Component reference

One row per Python module in `src/document_viewer/`. Source paths are
relative links from this document; click through to read the code.

For the container-level picture see [overview](overview.md); for an
end-to-end request trace see [data-flow](data-flow.md).

## API layer (`document_viewer.api`)

The FastAPI process. Handles auth, replay-guard, and queue dispatch. Runs no
parsers.

| Module | Purpose |
|---|---|
| [src/document_viewer/api/app.py](../../src/document_viewer/api/app.py) | FastAPI application factory and `viewer-api` console-script entrypoint; wires routers, middleware, and lifespan. |
| [src/document_viewer/api/deps.py](../../src/document_viewer/api/deps.py) | Dependency providers for `Settings`, the Redis pool, the arq pool, the JWT verifier, and the replay guard. |
| [src/document_viewer/api/middleware.py](../../src/document_viewer/api/middleware.py) | HTTP middleware: request ID injection and the uniform `{error, request_id}` error envelope. |
| [src/document_viewer/api/routes/health.py](../../src/document_viewer/api/routes/health.py) | Liveness (`/healthz`) and readiness (`/readyz`) endpoints. |
| [src/document_viewer/api/routes/render.py](../../src/document_viewer/api/routes/render.py) | `/render/{jwt}/manifest` and `/render/{jwt}/page/{n}` — JWT verify, replay-guard, enqueue, return. |
| [src/document_viewer/api/routes/embed.py](../../src/document_viewer/api/routes/embed.py) | Optional embeddable HTML+JS shell served at `/embed/{jwt}`. |

## Worker layer (`document_viewer.worker`)

The arq worker process. Pulls jobs, runs the pipeline, writes the cache.

| Module | Purpose |
|---|---|
| [src/document_viewer/worker/settings.py](../../src/document_viewer/worker/settings.py) | `arq` `WorkerSettings` and the `viewer-worker` console-script entrypoint; wires Redis settings and concurrency. |
| [src/document_viewer/worker/jobs.py](../../src/document_viewer/worker/jobs.py) | The `render_manifest` and `render_page` job functions — source fetch, mime detect, cache check, pipeline dispatch, cache write. |

## Render layer (`document_viewer.render`)

The actual rendering code. Pipeline-shaped; one module per stage.

| Module | Purpose |
|---|---|
| [src/document_viewer/render/pipeline.py](../../src/document_viewer/render/pipeline.py) | `RenderPipeline` dispatcher: routes a `RenderJob` to PDF or image rendering based on mime, applies the watermark, returns WebP bytes. |
| [src/document_viewer/render/pdf_clean.py](../../src/document_viewer/render/pdf_clean.py) | Defense-in-depth PDF sanitization via `pikepdf` — strips JavaScript, embedded files, auto-actions, launch actions, form submissions, and encryption before `pypdfium2` ever sees the file. |
| [src/document_viewer/render/pdf_render.py](../../src/document_viewer/render/pdf_render.py) | PDF page rasterization via `pypdfium2` (PDFium, Apache-2.0); exposes `PdfDocument` and `render_page` at a target width. |
| [src/document_viewer/render/image_pipeline.py](../../src/document_viewer/render/image_pipeline.py) | Image source pipeline: open with Pillow, strip metadata, resize, watermark, encode WebP. |
| [src/document_viewer/render/gotenberg_client.py](../../src/document_viewer/render/gotenberg_client.py) | Async HTTP client for Gotenberg's `/forms/libreoffice/convert` endpoint; the only place office formats are handled. |

## Shared layer (`document_viewer.shared`)

Code used by both the API and the worker. Pure-Python, no HTTP framework
dependencies.

| Module | Purpose |
|---|---|
| [src/document_viewer/shared/config.py](../../src/document_viewer/shared/config.py) | `Settings` — application configuration loaded from environment variables (pydantic-settings). |
| [src/document_viewer/shared/logging.py](../../src/document_viewer/shared/logging.py) | Structured JSON logging on stdout with PII redaction patterns; configured at process startup. |
| [src/document_viewer/shared/jwt_auth.py](../../src/document_viewer/shared/jwt_auth.py) | `JwtVerifier` (signature, expiry, issuer, required claims) and `JwtReplayGuard` (Redis SETNX with TTL = `exp - iat`). |
| [src/document_viewer/shared/source.py](../../src/document_viewer/shared/source.py) | `SourceBackend` protocol plus the `FilesystemBackend` and `S3Backend` implementations; selected by `SOURCE_BACKEND` env var. |
| [src/document_viewer/shared/mime.py](../../src/document_viewer/shared/mime.py) | Magic-byte mime detection over the first 4 KB via `python-magic`, with allowlist enforcement; extension is never trusted. |
| [src/document_viewer/shared/cache_keys.py](../../src/document_viewer/shared/cache_keys.py) | Deterministic cache key derivation: `page_key(etag, sub, page, width)` and `cleaned_pdf_key(etag, jti)`. |
| [src/document_viewer/shared/watermark.py](../../src/document_viewer/shared/watermark.py) | Server-side watermark rendering — diagonal tiled text baked into the pixel data via `PIL.ImageDraw`. |
| [src/document_viewer/shared/errors.py](../../src/document_viewer/shared/errors.py) | Domain error taxonomy (`RenderError` and friends); each maps to a stable HTTP status. |
