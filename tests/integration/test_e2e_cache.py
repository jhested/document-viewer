"""End-to-end: second page request hits cache (faster + same bytes)."""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import httpx

FIXTURE = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


def test_second_page_request_is_cached(
    upload_fixture: Callable[[str, Path], None],
    make_token: Callable[..., str],
    client: httpx.Client,
) -> None:
    upload_fixture("e2e/cache.pdf", FIXTURE)

    t1 = make_token("e2e/cache.pdf", sub="alice")
    t2 = make_token("e2e/cache.pdf", sub="alice")

    s1 = time.perf_counter()
    r1 = client.get(f"/render/{t1}/page/1?w=800")
    d1 = time.perf_counter() - s1
    assert r1.status_code == 200

    s2 = time.perf_counter()
    r2 = client.get(f"/render/{t2}/page/1?w=800")
    d2 = time.perf_counter() - s2
    assert r2.status_code == 200
    assert r1.content == r2.content
    # Cached request should be at least 3x faster
    assert d2 * 3 < d1 + 0.01
