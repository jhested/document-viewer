"""End-to-end: docx -> Gotenberg -> pikepdf -> pypdfium2 -> WebP."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "simple.docx"


@pytest.mark.skipif(
    not FIXTURE.exists(),
    reason="run `python tests/fixtures/_make_docx.py` (requires python-docx) first",
)
def test_docx_round_trip(
    upload_fixture: Callable[[str, Path], None],
    make_token: Callable[..., str],
    client: httpx.Client,
) -> None:
    key = "e2e/simple.docx"
    upload_fixture(key, FIXTURE)
    token = make_token(key)

    m = client.get(f"/render/{token}/manifest")
    assert m.status_code == 200
    body = m.json()
    assert body["pages"] >= 1
    assert "wordprocessingml" in body["mime"]

    p = client.get(f"/render/{make_token(key)}/page/1?w=800")
    assert p.status_code == 200
    assert p.content[:4] == b"RIFF"
