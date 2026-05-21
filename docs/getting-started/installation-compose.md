# Install with Docker Compose

This page covers a production-shaped Docker Compose deployment: building the two service images, pointing the worker at existing object storage, deciding whether to run Redis in-stack or out-of-stack, and putting an nginx reverse proxy in front for TLS termination.

For a five-minute laptop demo with MinIO bundled in, see [Quickstart](quickstart.md) instead.

## Prerequisites

- Linux host with Docker Engine 24+ and the `docker compose` plugin (Podman with `podman-compose` also works; the compose file is plain v2).
- Outbound network access to pull `redis:7-alpine`, `gotenberg/gotenberg:8`, and your built images.
- A reachable S3-compatible bucket containing the documents you want to render (AWS S3, MinIO, Ceph RGW, Wasabi, etc.) **or** a filesystem path mounted into the worker container.
- An ingress that can terminate TLS in front of the API. nginx is shown below; Traefik / Caddy / HAProxy all work the same way.
- A back-office system (or test script) that signs JWTs. See [Issuing tokens](../integration/issuing-tokens.md).

## Repository layout that matters

- [`compose.yaml`](../../compose.yaml) - production-shaped stack: `api`, `worker`, `gotenberg`, `redis`. Gotenberg is on an internal-only Docker network with `cap_drop: [ALL]`, `read_only: true`, and no internet route.
- [`compose.test.yaml`](../../compose.test.yaml) - overlay used for integration tests; adds a local MinIO. Do **not** use this overlay in production.
- [`services/api/Dockerfile`](../../services/api/Dockerfile) and [`services/worker/Dockerfile`](../../services/worker/Dockerfile) - image definitions. Both are multi-stage and produce non-root containers.
- [`.env.example`](../../.env.example) - every env var the app reads.

## Configuration via `.env`

Compose reads `./env` via `env_file: .env` on both `api` and `worker`. Copy the example and edit it:

```bash
cp .env.example .env
```

The variables fall into seven groups. Defaults in parentheses come from `src/document_viewer/shared/config.py`.

### Auth

| Variable | Required | Notes |
|---|---|---|
| `JWT_ALGORITHM` | yes | `HS256` for shared-secret deployments, `RS256` for production with an upstream signer. |
| `JWT_HMAC_SECRET` | if HS256 | Minimum 32 bytes. The project's test fixtures and tests refuse shorter secrets. |
| `JWT_PUBLIC_KEY` | if RS256 | PEM-encoded RSA public key. Verify-only; the private key never reaches the viewer. |
| `JWT_REQUIRED_ISS` | recommended | Hard-fails tokens whose `iss` claim does not match (e.g. `back-office`). |

### Source backend

| Variable | Required | Notes |
|---|---|---|
| `SOURCE_BACKEND` | yes | `s3` or `fs`. |
| `S3_ENDPOINT` | if s3 | Full URL incl. scheme (e.g. `https://s3.eu-west-1.amazonaws.com` or `http://minio:9000`). |
| `S3_BUCKET` | if s3 | Name of the bucket the worker reads from. Read-only credentials are sufficient. |
| `S3_REGION` | if s3 | Default `us-east-1`. Set to whatever your provider uses. |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | if s3 | Read-only credentials. Scope to `s3:GetObject` on the bucket prefix. |
| `FS_ROOT` | if fs | Absolute path inside the worker container. Bind-mount it read-only. |

### Redis

| Variable | Required | Notes |
|---|---|---|
| `REDIS_URL` | yes | `redis://host:6379/0`. Used for the arq job queue, the page cache, and the JWT replay guard. |

### Worker

| Variable | Default | Notes |
|---|---|---|
| `GOTENBERG_URL` | `http://gotenberg:3000` | Only used by the worker. |
| `WORKER_CONCURRENCY` | `4` | Concurrent renders per worker process. |

### Limits

| Variable | Default | Notes |
|---|---|---|
| `MAX_SOURCE_BYTES` | `104857600` | Hard cap on source size (100 MiB). |
| `MAX_PAGES` | `500` | Manifest fails over this. |
| `MAX_PAGE_WIDTH` | `2400` | Output width is clamped before rendering. |
| `RENDER_TIMEOUT_SECONDS` | `30` | Per-page rendering timeout. |
| `OFFICE_TIMEOUT_SECONDS` | `60` | Per-conversion timeout for Gotenberg calls. |

### Cache

| Variable | Default | Notes |
|---|---|---|
| `CACHE_TTL_SECONDS` | `900` | Page cache TTL. Match this to your JWT lifetime. |

### Watermark

| Variable | Default | Notes |
|---|---|---|
| `WATERMARK_OPACITY` | `0.18` | 0.0-1.0. |
| `WATERMARK_FONT_SIZE` | `24` | Points. |
| `WATERMARK_ANGLE` | `-30` | Degrees. |
| `WATERMARK_COLOR` | `#808080` | Any CSS-style hex colour. |

## Built-in Redis vs external Redis

`compose.yaml` ships a Redis container so the stack starts standalone. That is fine for single-host deployments where Redis dying with the rest of the stack is acceptable - the cache will rebuild on the next page request and short-lived JWT replay records expire naturally.

Move to an external Redis when you need any of:

- High availability (Sentinel or a managed Redis like ElastiCache).
- Memory-managed eviction with `maxmemory-policy allkeys-lru` pre-configured at the Redis side.
- Persistence policies you control independently from the document-viewer stack.
- Sharing one Redis with other services (use a dedicated DB index via `redis://host:6379/3`).

To switch, remove the `redis` service from `compose.yaml` (or override it with `compose.override.yaml`), drop its `depends_on` clauses, and set `REDIS_URL=redis://your-redis-host:6379/0` in `.env`. The app does not need any other change.

## Pointing at an existing S3 / Ceph / MinIO

Set:

```dotenv
SOURCE_BACKEND=s3
S3_ENDPOINT=https://s3.your-domain.example
S3_BUCKET=kyc-docs
S3_REGION=eu-west-1
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
```

The worker uses `aioboto3` and respects the standard AWS environment behaviour:

- Path-style addressing is auto-detected from the endpoint.
- For non-AWS endpoints (Ceph RGW, MinIO behind a corporate proxy), use the full HTTPS endpoint.
- Use a read-only IAM policy scoped to the bucket and (ideally) a key prefix. The worker never writes.

The JWT's `obj` claim is the S3 key. Pre-sign nothing - the viewer fetches with its own credentials.

## Filesystem backend (single-host or air-gapped)

For environments where the documents live on disk:

```dotenv
SOURCE_BACKEND=fs
FS_ROOT=/srv/docs
```

Bind-mount the directory **read-only** into the worker:

```yaml
services:
  worker:
    volumes:
      - /srv/docs:/srv/docs:ro
```

The implementation guards against `..` path traversal; the JWT's `obj` claim is treated as a path relative to `FS_ROOT`.

## Putting nginx in front for TLS

The `api` container speaks plain HTTP on `:8000`. In production it should sit behind a reverse proxy that terminates TLS and (optionally) drops the JWT from access logs.

Minimal nginx site:

```nginx
server {
    listen 443 ssl http2;
    server_name viewer.example.com;

    ssl_certificate     /etc/letsencrypt/live/viewer.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/viewer.example.com/privkey.pem;

    # JWTs end up in the URL path. Drop them from access logs.
    log_format viewer '$remote_addr - $remote_user [$time_local] '
                      '"$request_method $uri" $status $body_bytes_sent '
                      '"$http_referer" "$http_user_agent"';
    access_log /var/log/nginx/viewer.access.log viewer;

    client_max_body_size 0;     # only GETs; no uploads ever reach the API
    proxy_buffering off;        # stream WebP pages straight through

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}

server {
    listen 80;
    server_name viewer.example.com;
    return 301 https://$host$request_uri;
}
```

Note `$uri` rather than `$request` in the `log_format` - `$request` includes the query string, but the JWT is in the path itself, so neither variable hides it. Either log only `$request_method` (as above) or rotate/scrub logs aggressively. See `docs/security/hardening.md` for the full checklist.

If you put an ingress-level JWT validator (oauth2-proxy, Traefik plugin, nginx `auth_jwt` module) in front of the API, the API still re-validates the token. The viewer never trusts upstream-injected user headers in place of the JWT.

## Starting and verifying the stack

```bash
docker compose up -d
docker compose ps
docker compose logs -f api worker
```

Liveness and readiness probes are exposed by the API:

```bash
curl -sS http://localhost:8000/healthz
curl -sS http://localhost:8000/readyz
```

`/readyz` returns 200 only when Redis is reachable.

## Upgrading

```bash
git pull
docker compose pull         # if you use prebuilt images
docker compose build        # if you build locally
docker compose up -d
```

The `api` and `worker` deployments are stateless; a rolling restart is enough. Existing cache entries become stale but renew on the next page request. See `docs/operations/upgrades.md` for the compatibility matrix between chart version, app version, and Gotenberg version.
