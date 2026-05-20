"""End-to-end: PNG/JPEG source -> WebP page."""
from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import httpx
from PIL import Image


def test_jpeg_renders_single_page(
    tmp_path: Path,
    upload_fixture: Callable[[str, Path], None],
    make_token: Callable[..., str],
    client: httpx.Client,
) -> None:
    img = Image.new("RGB", (1600, 1200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    f = tmp_path / "img.jpg"
    f.write_bytes(buf.getvalue())
    upload_fixture("e2e/img.jpg", f)

    token = make_token("e2e/img.jpg")
    m = client.get(f"/render/{token}/manifest")
    assert m.status_code == 200
    assert m.json()["pages"] == 1
    p = client.get(f"/render/{make_token('e2e/img.jpg')}/page/1?w=800")
    assert p.status_code == 200
    assert p.content[:4] == b"RIFF"
