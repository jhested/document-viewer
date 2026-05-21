# Embedding rendered documents

There are three patterns for showing rendered pages in your reviewer UI. They
trade off complexity against control:

1. **Bare `<img>`** — simplest. One image tag per page; the JWT goes in the
   URL. Good when you already know the page count.
2. **`<iframe src="/embed/{jwt}">`** — bundled viewer. Lazy loading, zoom
   controls, page counter. Good for quick integrations and for reference.
3. **Custom JS** — full control. Fetch `/manifest`, build your own DOM, do
   your own lazy loading, intersperse review controls between pages.

In every pattern, **one JWT is consumed per HTTP request**. See
`docs/api/jwt.md` for replay-protection details and
`docs/integration/issuing-tokens.md` for signing snippets. The helper
`issueViewerToken` referenced below is from that page.

## Pattern 1 — Bare `<img>`

If you already know the page count (you stored it earlier, or you have a
fixed-shape document), just render one image per page. Each page is its own
request, so each needs its own JWT.

```html
<!-- Server-rendered HTML; each ${tokenN} was minted server-side for page N. -->
<img
  src="/render/${token1}/page/1?w=1200"
  alt="page 1"
  loading="lazy"
/>
<img
  src="/render/${token2}/page/2?w=1200"
  alt="page 2"
  loading="lazy"
/>
```

This is the only pattern where the JWT shows up in `document.referrer` and
browser history. That is fine — the tokens are short-lived and single-use —
but be aware of it.

## Pattern 2 — Bundled embed (`<iframe>`)

The viewer ships a tiny static page at `/embed/{jwt}` that handles loading,
zooming, and lazy rendering. It is the same code in
`services/embed/index.html` and `services/embed/main.js`. Drop it into an
iframe:

```html
<iframe
  src="/embed/${token}"
  style="width: 100%; height: 100vh; border: 0;"
  title="Document viewer"
></iframe>
```

The embed page calls `/render/{jwt}/manifest` for the page count and then
renders every page as `<img loading="lazy">`. The same JWT is reused for the
manifest call **and** every page request, so you must use **one fresh token
per browser session** and your replay window must cover the whole viewing
session (the JWT exists only in the URL of the embed page; each `/page/N`
request inside the embed reuses that same token).

If single-use replay is a hard requirement and you also want the bundled UI,
build pattern 3 instead — your server can mint a fresh token per page on
demand.

## Pattern 3 — Custom JS with `/manifest` + `/page`

This is what `services/embed/main.js` does internally. It is the right pattern
when you want to interleave review controls, virtualize the page list, or
mint a fresh token per page.

```html
<div id="pages"></div>
<script type="module">
  const pagesEl = document.getElementById("pages");

  // Ask your backend for a token bound to this document/page.
  // Implement `/api/viewer-token` to call `issueViewerToken(...)` from
  // docs/integration/issuing-tokens.md and return `{ token }` as JSON.
  async function mintToken({ page = null } = {}) {
    const res = await fetch("/api/viewer-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page }),
    });
    if (!res.ok) throw new Error(`mint ${res.status}`);
    const { token } = await res.json();
    return token;
  }

  async function load() {
    const manifestToken = await mintToken();
    const manifest = await fetch(
      `/render/${encodeURIComponent(manifestToken)}/manifest`
    ).then((r) => {
      if (!r.ok) throw new Error(`manifest ${r.status}`);
      return r.json();
    });

    for (let p = 1; p <= manifest.pages; p++) {
      const img = document.createElement("img");
      img.loading = "lazy";
      img.alt = `page ${p}`;
      // One token per page request — replay-safe.
      const pageToken = await mintToken({ page: p });
      img.src = `/render/${encodeURIComponent(pageToken)}/page/${p}?w=1200`;
      pagesEl.appendChild(img);
    }
  }

  load().catch((e) => {
    pagesEl.textContent = `error: ${e.message}`;
  });
</script>
```

### Zoom

Re-request the same page with a different `w` query parameter. The server
clamps to `MAX_PAGE_WIDTH` (default 2400). Picking `w` around the rendered CSS
pixel width times the device pixel ratio gives sharp output without wasted
bytes.

```javascript
function pageUrl(token, n, cssPixels) {
  const w = Math.min(2400, Math.round(cssPixels * (window.devicePixelRatio || 1)));
  return `/render/${encodeURIComponent(token)}/page/${n}?w=${w}`;
}
```

## A note on caching

Every render response is served with `Cache-Control: no-store`. Do not put a
shared CDN in front of `/render/*` — the response bodies are per-user PII
with the reviewer's identity baked into the watermark.
