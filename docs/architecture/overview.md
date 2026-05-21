# Architecture overview

`document-viewer` is a small set of cooperating containers behind a single HTTP
surface. The design splits trust boundaries deliberately: parsers never touch
the network-facing process, the JWT-facing process never touches parsers, and
the riskiest parser of all (LibreOffice) runs in a separate, hardened,
egress-denied container.

This page lists every container, what it does, and how it talks to the others.
For an end-to-end request trace see [data-flow](data-flow.md). For a per-module
breakdown see [component-reference](component-reference.md).

## Topology

```text
                ┌──────────────────────────┐
   ingress ───► │  viewer-api  (FastAPI)   │ ── verifies JWT
   (nginx /     │  - auth, routing         │ ── replay-guard via Redis SETNX
    traefik)    │  - serves rendered pages │ ── cache lookup
                │  - serves embed shell    │ ── enqueues render jobs (arq)
                └────────┬─────────────────┘
                         │
                         ▼
                ┌──────────────────────────┐
                │  redis                   │ ── arq job queue
                │  - queue + cache         │ ── WebP page cache (allkeys-lru)
                │  - JWT replay set        │ ── jti SETNX with TTL
                └────────┬─────────────────┘
                         │
                         ▼
                ┌──────────────────────────┐
                │  viewer-worker (Python)  │ ── pulls source from S3/FS
                │  - mime detect           │ ── pikepdf clean
                │  - PDF pipeline          │ ── pypdfium2 render
                │  - image pipeline        │ ── Pillow re-encode + watermark
                │  - cache writes          │ ── encode WebP, store in Redis
                └────────┬─────────────────┘
                         │ HTTP multipart
                         │ (office formats only)
                         ▼
                ┌──────────────────────────────┐
                │ gotenberg  (upstream image)  │ ── gotenberg/gotenberg:8
                │ - office → PDF via           │ ── /forms/libreoffice/convert
                │   LibreOffice               │ ── stateless HTTP
                │ - hardened by orchestrator:  │ ── no shared volume
                │   no egress, ro fs, no caps  │
                └──────────────────────────────┘

                ┌──────────────────────────┐
                │  S3 / MinIO / Ceph / FS  │ ── source object store
                │  (operator-supplied)     │ ── worker has read-only creds
                └──────────────────────────┘
```

## Containers

### `viewer-api`

A FastAPI application that handles every external request. It does three jobs
and nothing else:

1. Verify the incoming JWT (signature, expiry, issuer, required claims).
2. Replay-protect the token by recording `jti` in Redis with `SETNX` and TTL
   equal to `exp - iat`. A second use of the same token returns 401.
3. Enqueue a render job onto the `arq` Redis-backed queue and stream back the
   result.

`viewer-api` runs no parsers. It never touches source bytes. Its only outbound
dependency is Redis. If Gotenberg or the source store is unreachable that
shows up as a worker-side failure surfaced as a 5xx — the API itself stays
healthy.

The API also serves the optional embed shell at `/embed/{jwt}` and the
liveness/readiness probes at `/healthz` and `/readyz`.

### `viewer-worker`

A long-running Python process that pulls jobs off the `arq` queue and executes
the render pipeline. For each job it:

- Streams the source object from the configured backend (S3 or filesystem) and
  collects the bytes in memory, bounded by `MAX_SOURCE_BYTES`.
- Detects the mime type from the first 4 KB via `python-magic` and rejects
  anything outside the allowlist.
- Dispatches by mime: PDFs go through `pikepdf` sanitization then `pypdfium2`
  rasterization; office formats are POSTed to Gotenberg first, then the
  returned PDF goes through the same PDF pipeline; raster images go through
  Pillow.
- Bakes the per-user watermark into the pixel data, encodes WebP, and writes
  the result to Redis under a deterministic per-user cache key.

The worker has read-only credentials for the source store, network access to
Redis and Gotenberg, and nothing else. Render concurrency is set by
`WORKER_CONCURRENCY`.

### `gotenberg`

The upstream `gotenberg/gotenberg:8` image, pinned by digest. It exposes a
single endpoint we use: `POST /forms/libreoffice/convert`. The worker streams
an office file in the multipart body and reads the converted PDF from the
response.

This is the highest-risk container in the system — it runs LibreOffice on
untrusted input — so it is the most heavily isolated:

- `read_only: true`, tmpfs for `/tmp`, all capabilities dropped,
  `no-new-privileges`.
- On Compose: attached to an internal Docker network with no internet route.
- On Kubernetes: a `NetworkPolicy` denies all egress and allows ingress only
  from `viewer-worker` pods.
- Memory and CPU limits applied; periodic restart to flush any accumulated
  state.

Gotenberg is invoked only for office mimes. For native PDFs and raster images
it sits idle.

### `redis`

A single Redis instance serving three roles:

- The `arq` job queue (worker pulls, API pushes).
- The page cache: WebP bytes keyed by
  `page:{sha256(etag|sub|page|width)}`, with `maxmemory-policy
  allkeys-lru`, default TTL 900 s.
- The JWT replay set: `jti` SETNX with TTL = remaining token lifetime.

Redis is internal. Nothing outside the deployment talks to it.

### Source store (optional, operator-supplied)

The worker reads source documents from an object store. Two backends ship in
the box, selected by `SOURCE_BACKEND`:

- `S3Backend` (default) talks to S3, MinIO, or Ceph via `aioboto3` with a
  configurable endpoint URL.
- `FilesystemBackend` reads from a configured directory, with a traversal
  guard. Intended for dev and tests.

A third backend (Azure Blob, GCS, etc.) is one new class plus config — no
other code changes.

## Communication summary

| From | To | Protocol | Notes |
|---|---|---|---|
| client | `viewer-api` | HTTPS | terminated at ingress |
| `viewer-api` | `redis` | TCP | queue push, replay-guard, cache reads |
| `viewer-worker` | `redis` | TCP | queue pull, cache writes |
| `viewer-worker` | source store | HTTPS (S3) or filesystem | read-only |
| `viewer-worker` | `gotenberg` | HTTP multipart | office formats only |
| `gotenberg` | anywhere | none | egress denied by orchestrator |

## Why this shape

The split-process design is the load-bearing security property. A
malicious-PDF exploit that lands code execution in the worker cannot reach the
ingress-facing process, the JWT verification keys, or the user. A malicious
office file that lands code execution inside Gotenberg cannot reach the
network at all. The API is small enough to audit by eye; the worker can be
restarted on any error without affecting in-flight requests.
