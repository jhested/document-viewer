(() => {
  const script = document.currentScript;
  const token = script.dataset.token;
  const pagesEl = document.getElementById("pages");
  const status = document.getElementById("status");
  let width = 1200;
  let pageCount = 0;

  function renderPages() {
    pagesEl.replaceChildren();
    for (let p = 1; p <= pageCount; p++) {
      const img = document.createElement("img");
      img.className = "page";
      img.loading = "lazy";
      img.src = `/render/${encodeURIComponent(token)}/page/${p}?w=${width}`;
      pagesEl.appendChild(img);
    }
    status.textContent = `${pageCount} pages, ${width}px`;
  }

  async function loadManifestThenPages() {
    status.textContent = "loading...";
    const manifest = await fetch(`/render/${encodeURIComponent(token)}/manifest`).then(r => {
      if (!r.ok) throw new Error(`manifest ${r.status}`);
      return r.json();
    });
    pageCount = manifest.pages;
    renderPages();
  }

  document.getElementById("zoom-in").onclick = () => {
    if (!pageCount) return;
    width = Math.min(width + 200, 2400);
    renderPages();
  };
  document.getElementById("zoom-out").onclick = () => {
    if (!pageCount) return;
    width = Math.max(width - 200, 400);
    renderPages();
  };

  loadManifestThenPages().catch(e => { status.textContent = `error: ${e.message}`; });
})();
