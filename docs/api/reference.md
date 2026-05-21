# API reference

The document-viewer API is a small, JWT-gated HTTP surface that renders documents
to watermarked WebP images. The JWT travels in the URL path so each rendered page
can be embedded directly as an `<img src>`. All render responses are served with
`Cache-Default: no-store` — every render is per-user PII and must not be reused
across users or stored in shared caches.

Source: `src/document_viewer/api/routes/health.py`,
`src/document_viewer/api/routes/render.py`,
`src/document_viewer/api/routes/embed.py`.

## Common conventions

- **JWT location.** Every render and embed endpoint takes the token as a path
  segment, not as a header or query parameter. This is what lets a token-bound
  page be referenced as `<img src="/render/{jwt}/page/1">`.
- **Replay protection.** Every successful verify performs a Redis `SETNX` on the
  token's `jti`. The first use wins; subsequent uses return `401 token replayed`.
  See `docs/api/jwt.md`.
- **Caching.** All render responses include `Cache-Control: no-store`. Browser
  caches, CDNs, and shared proxies must not retain rendered bytes.
- **Request ID.** Every response carries an `X-Request-ID` header. The API will
  generate one if the request did not provide it. Error bodies include the same
  ID under `request_id` so an operator can correlate a client failure to a
  server-side log line.
- **Error envelope.** Error responses use a uniform JSON shape:
  ```json
  {"error": "token expired", "request_id": "b3f1a2..."}
  ```

## Endpoints

### `GET /healthz`

Liveness probe. Returns 200 as long as the process is running.

- **Auth:** none.
- **Response 200:**
  ```json
  {"status": "ok"}
  ```

### `GET /readyz`

Readiness probe. Pings Redis. Returns 200 if Redis answered; the body's `status`
field is `ok` when the ping succeeded and `degraded` otherwise.

- **Auth:** none.
- **Response 200 (Redis reachable):**
  ```json
  {"status": "ok"}
  ```
- **Response 200 (Redis answered but not healthy):**
  ```json
  {"status": "degraded"}
  ```

### `GET /render/{jwt}/manifest`

Returns metadata about the source document: detected mime, page count, page
dimensions, and the source object's ETag. The first call to `/manifest` for an
office source triggers the LibreOffice conversion, which is cached for the
manifest TTL; subsequent `/page` requests reuse the cached intermediate PDF.

- **Path params:**
  - `jwt` — a signed token (see `docs/api/jwt.md`).
- **Query params:** none.
- **Response headers:**
  - `Content-Type: application/json`
  - `Cache-Control: no-store`
  - `X-Request-ID: <hex>`
- **Response 200:**
  ```json
  {
    "mime": "application/pdf",
    "pages": 12,
    "dims": [{"w": 1700, "h": 2200}, {"w": 1700, "h": 2200}],
    "etag": "sha256:f5d8...",
    "ttl_seconds": 900
  }
  ```
  `dims` is a list of `{w, h}` pairs in PDF points (or `0, 0` for image
  sources). `ttl_seconds` is the cache TTL the server applied to derived
  artifacts.

### `GET /render/{jwt}/page/{n}`

Returns a single rendered page as a watermarked WebP.

- **Path params:**
  - `jwt` — signed token.
  - `n` — 1-indexed page number.
- **Query params:**
  - `w` — requested image width in pixels. Optional. Default `1200`. The server
    clamps to `[1, MAX_PAGE_WIDTH]` (default `MAX_PAGE_WIDTH=2400`). DPI is
    derived from the clamped width.
- **Response headers:**
  - `Content-Type: image/webp`
  - `Cache-Control: no-store`
  - `X-Request-ID: <hex>`
- **Response 200:** raw WebP bytes.

### `GET /embed/{jwt}`

Returns a static HTML page that bootstraps `main.js` with the token bound to a
`data-token` attribute. The script fetches `/manifest` and renders every page as
a lazy-loaded `<img>` with zoom controls.

- **Path params:**
  - `jwt` — signed token.
- **Response headers:**
  - `Content-Type: text/html`
- **Response 200:** an HTML document. The JWT is JSON-escaped before being
  inlined, so quote- or backslash-bearing tokens remain attribute-safe.

### `GET /embed/main.js`

The JavaScript file that the embed page references. Served from
`services/embed/main.js`.

- **Auth:** none (the script is harmless on its own; the token lives in the
  embedding page).
- **Response headers:**
  - `Content-Type: application/javascript`
- **Response 200:** raw JavaScript.

## Error catalog

All error responses share the same JSON envelope and headers:

```json
{"error": "<short message>", "request_id": "<hex>"}
```

with `Cache-Control: no-store` and `X-Request-ID: <hex>`.

| Status | When it is returned |
|---|---|
| `401` `token expired` | The JWT's `exp` is in the past. |
| `401` `token invalid` | Signature, issuer, algorithm, or required claim failed verification. |
| `401` `token replayed` | The token's `jti` has already been consumed via Redis `SETNX`. |
| `404` | Page out of range (`n < 1` or `n > pages`), or source object not found in the configured backend. |
| `413` | Source object exceeds `MAX_SOURCE_BYTES` (default 100 MiB). |
| `415` | Detected mime is not in `ALLOWED_MIMES`. The server uses magic-byte sniffing — declared content-types from upstream storage are not trusted. |
| `503` | Job queue is unavailable, or all workers are busy. |
| `504` | Per-page render exceeded `RENDER_TIMEOUT_SECONDS` (default 30s) or `OFFICE_TIMEOUT_SECONDS` (default 60s) for office conversions. |
| `500` | Unhandled worker failure (crash, OOM, unexpected exception). The response body's `request_id` correlates to the server log entry. |

## Related reading

- `docs/api/jwt.md` — token claims, signing algorithms, key/secret rotation.
- `docs/integration/issuing-tokens.md` — server-side signing in Python and
  Node.js.
- `docs/integration/embedding.md` — three integration patterns.
