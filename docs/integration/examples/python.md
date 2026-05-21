# Python example: mint, fetch, save

A complete, runnable script. It issues an HS256 token, calls
`/render/{jwt}/manifest`, then calls `/render/{jwt}/page/1` and writes the
WebP to disk.

The script uses two tokens — one for the manifest and one for page 1 —
because the viewer's replay guard consumes the `jti` on first use. See
`docs/api/jwt.md`.

## Prerequisites

```bash
pip install PyJWT requests
```

A running document-viewer (compose or helm) reachable at
`http://localhost:8000`, configured with `JWT_ALGORITHM=HS256` and the same
`JWT_HMAC_SECRET` you put in the script.

## Script

```python
"""Mint two viewer tokens, fetch the manifest, save page 1 as WebP."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import jwt  # PyJWT
import requests

# --- config -----------------------------------------------------------------

VIEWER_BASE = "http://localhost:8000"
SECRET = "your-32-byte-or-longer-jwt-secret-here"  # must match the viewer's JWT_HMAC_SECRET

ISSUER = "kyc-reviewer-api"
USER = "agent-42@example.com"
OBJECT_KEY = "cases/2026/05/case-9912/passport.pdf"
CASE_ID = "CASE-9912"

OUTPUT_PATH = Path("page-1.webp")


# --- helpers ----------------------------------------------------------------

def issue_token(*, ttl_seconds: int = 300) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": USER,
        "obj": OBJECT_KEY,
        "case": CASE_ID,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")


def fetch_manifest(token: str) -> dict:
    url = f"{VIEWER_BASE}/render/{token}/manifest"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_page(token: str, n: int, *, width: int = 1200) -> bytes:
    url = f"{VIEWER_BASE}/render/{token}/page/{n}"
    r = requests.get(url, params={"w": width}, timeout=30)
    r.raise_for_status()
    return r.content


# --- main -------------------------------------------------------------------

def main() -> None:
    manifest_token = issue_token()
    manifest = fetch_manifest(manifest_token)
    print(
        f"manifest: mime={manifest['mime']} pages={manifest['pages']} "
        f"etag={manifest['etag']} ttl={manifest['ttl_seconds']}s"
    )

    if manifest["pages"] < 1:
        raise SystemExit("document has no pages")

    page_token = issue_token()
    webp = fetch_page(page_token, 1, width=1200)
    OUTPUT_PATH.write_bytes(webp)
    print(f"wrote {len(webp)} bytes to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

## Running

```bash
python save_page_1.py
```

Expected output:

```
manifest: mime=application/pdf pages=12 etag=sha256:... ttl=900s
wrote 84231 bytes to page-1.webp
```

Open `page-1.webp` in any modern image viewer.

## Saving every page

Loop through `manifest["pages"]`, minting a fresh token for each page:

```python
for n in range(1, manifest["pages"] + 1):
    token = issue_token()
    webp = fetch_page(token, n, width=1200)
    Path(f"page-{n}.webp").write_bytes(webp)
```

## Troubleshooting

- `401 token invalid` — check `SECRET` matches the viewer's `JWT_HMAC_SECRET`
  exactly, and that `JWT_ALGORITHM` is `HS256` on the viewer.
- `401 token replayed` — you reused the same token (probably across the
  manifest + page calls). Mint one per request.
- `415` — the source object's detected mime is not in the allowlist. The
  viewer sniffs magic bytes; the storage backend's declared content-type is
  ignored. Confirm the actual file contents.
- `413` — the source exceeds `MAX_SOURCE_BYTES` (default 100 MiB).
- `504` — render exceeded `RENDER_TIMEOUT_SECONDS` (default 30s). Large
  scanned PDFs or huge office documents can hit this; see
  `docs/operations/tuning.md` once it exists.
