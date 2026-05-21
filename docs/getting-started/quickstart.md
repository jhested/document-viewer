# Quickstart

A five-minute walkthrough that gets `document-viewer` running on your laptop with Docker Compose, uploads a sample PDF to MinIO, mints a JWT, and opens the rendered document in a browser.

You will need:

- Docker Engine 24+ with the `docker compose` plugin
- Python 3.10+ (only used here to mint a JWT)
- About 2 GB of free disk for the container images

## 1. Clone and start the stack

```bash
git clone https://github.com/OWNER/document-viewer.git
cd document-viewer
cp .env.example .env
docker compose -f compose.yaml -f compose.test.yaml up -d
```

`compose.yaml` defines the production-shaped services (`api`, `worker`, `gotenberg`, `redis`). `compose.test.yaml` layers a local MinIO on top so you have an S3-compatible store to upload into. See [`compose.yaml`](../../compose.yaml) and [`compose.test.yaml`](../../compose.test.yaml) for the exact definitions.

Wait until all containers report healthy:

```bash
docker compose -f compose.yaml -f compose.test.yaml ps
```

The API listens on `http://localhost:8000`, MinIO on `http://localhost:9000` (S3 API) and `http://localhost:9001` (web console).

## 2. Install the MinIO client (`mc`)

`mc` is the official MinIO CLI; we use it to create the bucket and upload a sample file. If you already have it, skip to the next step.

```bash
# Linux x86_64
curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /tmp/mc
chmod +x /tmp/mc
sudo mv /tmp/mc /usr/local/bin/mc

# macOS (Homebrew)
brew install minio/stable/mc
```

Confirm it works:

```bash
mc --version
```

## 3. Create the bucket and upload a sample PDF

Register the local MinIO under an alias called `local`. The credentials match `compose.test.yaml`:

```bash
mc alias set local http://localhost:9000 minio-user minio-password
mc mb --ignore-existing local/kyc-docs
```

Drop any PDF you have lying around into the bucket. We will store it under the key `samples/hello.pdf`:

```bash
mc cp /path/to/your/sample.pdf local/kyc-docs/samples/hello.pdf
```

You can also use the MinIO web console at `http://localhost:9001` (same credentials) if you prefer point-and-click.

## 4. Mint a JWT

The API accepts a stateless JWT scoped to one object and one user. With the default `compose.test.yaml`, the algorithm is HS256 and the secret is `test-secret-must-be-at-least-32-bytes-long!!`. The `.env.example` you copied uses HS256 too, but with the placeholder secret `change-me-to-a-long-random-secret`; for this quickstart we line up with `compose.test.yaml` so MinIO + API agree.

Install PyJWT in a throwaway virtualenv:

```bash
python3 -m venv /tmp/dv-venv
/tmp/dv-venv/bin/pip install --quiet 'pyjwt>=2.8'
```

Mint a token good for ten minutes:

```bash
/tmp/dv-venv/bin/python - <<'PY'
import time, uuid, jwt

SECRET = "test-secret-must-be-at-least-32-bytes-long!!"
now = int(time.time())
payload = {
    "iss": "back-office",
    "sub": "alice@bank.com",
    "obj": "samples/hello.pdf",
    "case": "case-123",
    "iat": now,
    "exp": now + 600,
    "jti": str(uuid.uuid4()),
}
print(jwt.encode(payload, SECRET, algorithm="HS256"))
PY
```

Copy the printed token into a shell variable so the rest of the commands stay readable:

```bash
TOKEN="paste-the-printed-jwt-here"
```

The secret must be at least 32 bytes; shorter secrets are rejected by the project's test config and are a bad idea regardless.

## 5. Render the document

Open the embed shell in a browser:

```bash
xdg-open "http://localhost:8000/embed/${TOKEN}" 2>/dev/null \
  || open "http://localhost:8000/embed/${TOKEN}" 2>/dev/null \
  || echo "Browse to http://localhost:8000/embed/${TOKEN}"
```

The shell calls `/render/{jwt}/manifest`, then lazy-loads one `<img>` per page, watermarked with the `sub` and `case` from the token.

Prefer raw HTTP? Hit the endpoints directly:

```bash
curl -sS "http://localhost:8000/render/${TOKEN}/manifest" | python -m json.tool
curl -sS "http://localhost:8000/render/${TOKEN}/page/1?w=1200" --output page1.webp
```

Tokens are single-use: replaying the same `jti` returns `401`. Mint a fresh one if you want to hit the endpoints again.

## 6. Tear down

```bash
docker compose -f compose.yaml -f compose.test.yaml down -v
```

The `-v` flag also clears MinIO's data volume.

## Where to next

- [Compose install](installation-compose.md) - production-shaped Compose deployment in front of an existing S3 / Ceph and an nginx terminator.
- [Helm install](installation-helm.md) - Kubernetes deployment using the chart under `helm/document-viewer/`.
- [Configuration reference](../operations/configuration.md) - every env var the app understands.
- [Issuing tokens](../integration/issuing-tokens.md) - how a back-office app should sign JWTs in production (RS256 recommended).
