# Node.js example: mint, fetch, save

A complete, runnable Node.js script. It issues an HS256 token, calls
`/render/{jwt}/manifest`, then calls `/render/{jwt}/page/1` and writes the
WebP to disk.

The script uses two tokens — one for the manifest and one for page 1 —
because the viewer's replay guard consumes the `jti` on first use. See
`docs/api/jwt.md`.

## Prerequisites

- Node.js 20 or later (global `fetch` is built in).
- A running document-viewer reachable at `http://localhost:8000`,
  configured with `JWT_ALGORITHM=HS256` and the same `JWT_HMAC_SECRET`
  you put in the script.

```bash
npm init -y
npm install jsonwebtoken
```

If your `package.json` is not already ESM, add `"type": "module"` to it so
that `import` works.

## Script

```javascript
// save-page-1.mjs — mint two viewer tokens, fetch the manifest, save page 1.
import jwt from "jsonwebtoken";
import { randomUUID } from "node:crypto";
import { writeFile } from "node:fs/promises";

// --- config ----------------------------------------------------------------

const VIEWER_BASE = "http://localhost:8000";
const SECRET = "your-32-byte-or-longer-jwt-secret-here"; // must match viewer's JWT_HMAC_SECRET

const ISSUER = "kyc-reviewer-api";
const USER = "agent-42@example.com";
const OBJECT_KEY = "cases/2026/05/case-9912/passport.pdf";
const CASE_ID = "CASE-9912";

const OUTPUT_PATH = "page-1.webp";

// --- helpers ---------------------------------------------------------------

function issueToken({ ttlSeconds = 300 } = {}) {
  const now = Math.floor(Date.now() / 1000);
  const claims = {
    iss: ISSUER,
    sub: USER,
    obj: OBJECT_KEY,
    case: CASE_ID,
    jti: randomUUID().replace(/-/g, ""),
    iat: now,
    exp: now + ttlSeconds,
  };
  return jwt.sign(claims, SECRET, { algorithm: "HS256" });
}

async function fetchManifest(token) {
  const url = `${VIEWER_BASE}/render/${token}/manifest`;
  const r = await fetch(url);
  if (!r.ok) {
    throw new Error(`manifest ${r.status}: ${await r.text()}`);
  }
  return r.json();
}

async function fetchPage(token, n, { width = 1200 } = {}) {
  const url = `${VIEWER_BASE}/render/${token}/page/${n}?w=${width}`;
  const r = await fetch(url);
  if (!r.ok) {
    throw new Error(`page ${r.status}: ${await r.text()}`);
  }
  return Buffer.from(await r.arrayBuffer());
}

// --- main ------------------------------------------------------------------

async function main() {
  const manifestToken = issueToken();
  const manifest = await fetchManifest(manifestToken);
  console.log(
    `manifest: mime=${manifest.mime} pages=${manifest.pages} ` +
      `etag=${manifest.etag} ttl=${manifest.ttl_seconds}s`
  );

  if (manifest.pages < 1) {
    throw new Error("document has no pages");
  }

  const pageToken = issueToken();
  const webp = await fetchPage(pageToken, 1, { width: 1200 });
  await writeFile(OUTPUT_PATH, webp);
  console.log(`wrote ${webp.length} bytes to ${OUTPUT_PATH}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
```

## Running

```bash
node save-page-1.mjs
```

Expected output:

```
manifest: mime=application/pdf pages=12 etag=sha256:... ttl=900s
wrote 84231 bytes to page-1.webp
```

## Saving every page

```javascript
for (let n = 1; n <= manifest.pages; n++) {
  const token = issueToken();
  const webp = await fetchPage(token, n, { width: 1200 });
  await writeFile(`page-${n}.webp`, webp);
}
```

## Troubleshooting

- `401 token invalid` — verify `SECRET` matches `JWT_HMAC_SECRET` exactly, and
  that the viewer's `JWT_ALGORITHM` is `HS256`.
- `401 token replayed` — you reused the same token across the manifest and
  page calls. Mint one per request.
- `415` — the source object's sniffed mime is not in the allowlist.
- `413` — source exceeds `MAX_SOURCE_BYTES` (default 100 MiB).
- `504` — render exceeded `RENDER_TIMEOUT_SECONDS` (default 30s).
