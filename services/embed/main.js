(() => {
  const script = document.currentScript;
  const token = script.dataset.token;
  const pagesEl = document.getElementById("pages");
  const status = document.getElementById("status");
  let width = 1200;

  async function load() {
    status.textContent = "loading...";
    pagesEl.replaceChildren();
    const manifest = await fetch(`/render/${encodeURIComponent(token)}/manifest`).then(r => {
      if (!r.ok) throw new Error(`manifest ${r.status}`);
      return r.json();
    });
    for (let p = 1; p <= manifest.pages; p++) {
      const img = document.createElement("img");
      img.className = "page";
      img.loading = "lazy";
      img.src = `/render/${encodeURIComponent(token)}/page/${p}?w=${width}`;
      pagesEl.appendChild(img);
    }
    status.textContent = `${manifest.pages} pages`;
  }

  document.getElementById("zoom-in").onclick = () => { width = Math.min(width + 200, 2400); load(); };
  document.getElementById("zoom-out").onclick = () => { width = Math.max(width - 200, 400); load(); };

  load().catch(e => { status.textContent = `error: ${e.message}`; });
})();
