# Deployment: Docker Compose

This runbook covers a single-host Docker Compose deployment using the
top-level `compose.yaml`. The same file is used in production-like staging
environments; the integration test stack lives in `compose.test.yaml` and is
intended for CI only.

## Prerequisites

- Docker Engine 24+ with the Compose v2 plugin (`docker compose version`
  must return v2.x).
- Outbound network access to the container registries hosting the API,
  worker, Gotenberg, and Redis images at install time.
- A reachable Redis instance. The bundled `redis` service is fine for
  single-host deployments; for HA, point `REDIS_URL` at an external Redis
  and remove the `redis` service.
- A reachable object store (S3, MinIO, Ceph, or equivalent) or a directory
  on disk if `SOURCE_BACKEND=fs`.

## Configure

Copy `.env.example` to `.env` and fill in every uncommented value:

```bash
cp .env.example .env
$EDITOR .env
```

At minimum, set:

- `JWT_ALGORITHM` (`RS256` in production)
- `JWT_PUBLIC_KEY` (for `RS256`) or `JWT_HMAC_SECRET` (for `HS256`)
- `JWT_REQUIRED_ISS` to the back-office service name
- `REDIS_URL`
- `SOURCE_BACKEND` and its associated `S3_*` or `FS_ROOT` values

The file is loaded by both API and worker services via `env_file: .env` in
`compose.yaml`. Restrict its filesystem permissions:

```bash
chmod 600 .env
```

## Pin all images by digest

The `compose.yaml` pins Gotenberg by digest using a placeholder; the
placeholder must be replaced before the first start:

```yaml
gotenberg:
  image: gotenberg/gotenberg:8@sha256:CHANGE-ME-TO-DIGEST
```

Look up the digest for the desired tag and patch the file:

```bash
docker buildx imagetools inspect gotenberg/gotenberg:8 \
  --format '{{json .Manifest.Digest}}'
```

Use the returned `sha256:...` value to replace `CHANGE-ME-TO-DIGEST`. Do
the same exercise for `redis:7-alpine` and for your own `api` and `worker`
images if you build and push them rather than building locally each time.

## Start

```bash
docker compose pull
docker compose up -d
docker compose ps
```

The API listens on `0.0.0.0:8000`. Verify it is reachable:

```bash
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
```

Both must return `200 OK`. `/readyz` only returns `200` once the API can
talk to Redis.

## Backups

There is nothing to back up by design.

- **Sources** live in S3 (or an operator-managed filesystem). The viewer
  never writes to that location and treats it as read-only.
- **Cache** in Redis is ephemeral. Every entry has a TTL of
  `CACHE_TTL_SECONDS` (default 15 minutes). Losing it costs CPU on the next
  request; it does not lose data.
- **Application state** is zero. The API and worker pods are stateless and
  can be recreated freely.

If you replaced the bundled Redis with a managed Redis, follow that
provider's backup advice; that is the only thing in the system worth
backing up, and only if you want to preserve warm caches across host
rebuilds.

## Log shipping

The API and worker both write structured JSON logs to `stdout`
(`document_viewer.shared.logging`). Each log line is a single JSON object
keyed by `event`, with `timestamp` and `level` always present.

To ship to a central log store, run a sidecar log collector
(`vector`, `fluent-bit`, `promtail`) on the host with the Docker socket
mounted, or use the Docker logging driver of choice:

```yaml
api:
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "5"
```

Reload with `docker compose up -d --force-recreate api worker`.

Do not enable verbose request body logging. The application redacts JWTs
from logged strings via `_Logger.redact`, but the safest default is to log
events, not payloads.

## Secrets rotation

### JWT (HS256)

For HMAC tokens, the secret is shared with the back-office issuer.
Recommended rotation:

1. Generate a new long random secret on the issuer.
2. Configure the issuer to start signing with the new secret while still
   accepting either secret for a grace window equal to the longest expected
   token lifetime (typically a few minutes).
3. Update `.env` on the viewer host with the new `JWT_HMAC_SECRET`.
4. Recreate the API container:
   ```bash
   docker compose up -d --force-recreate api
   ```
5. Purge the Redis JWT replay-guard keys so the new tokens have a clean
   slate (optional; they expire on their own):
   ```bash
   docker compose exec redis redis-cli --scan --pattern 'jti:*' | \
     xargs -r docker compose exec -T redis redis-cli del
   ```
6. Drop the old secret on the issuer.

### JWT (RS256)

For RSA tokens, the viewer holds only the public key. Rotation is the
issuer's responsibility; the viewer's job is to publish the new public key
in `JWT_PUBLIC_KEY` and reload:

```bash
docker compose up -d --force-recreate api
```

If you support multiple key IDs simultaneously (recommended for
zero-downtime rotation), you'll need to extend `jwt_auth` to accept a key
set; the current code accepts a single public key.

### S3 credentials

1. Issue new keys for the read-only role/user on the object store.
2. Update `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` in `.env`.
3. Recreate the worker (the API does not touch S3):
   ```bash
   docker compose up -d --force-recreate worker
   ```
4. Revoke the old keys.

## Upgrades

See [upgrades.md](upgrades.md) for the chart/app/Gotenberg compatibility
matrix. For Compose, the upgrade procedure is:

```bash
docker compose pull
docker compose up -d
```

Compose recreates only containers whose image digest changed.
