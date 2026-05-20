"""End-to-end: PDF source -> manifest -> page render."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx

FIXTURE = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


def test_pdf_manifest_and_first_page(
    upload_fixture: Callable[[str, Path], None],
    make_token: Callable[..., str],
    client: httpx.Client,
) -> None:
    key = "e2e/simple.pdf"
    upload_fixture(key, FIXTURE)
    token = make_token(key)

    m = client.get(f"/render/{token}/manifest")
    assert m.status_code == 200, m.text
    assert m.headers["cache-control"] == "no-store"
    body = m.json()
    assert body["pages"] == 3
    assert body["mime"] == "application/pdf"

    p = client.get(f"/render/{make_token(key)}/page/1?w=800")
    assert p.status_code == 200
    assert p.headers["content-type"] == "image/webp"
    assert p.content[:4] == b"RIFF"
