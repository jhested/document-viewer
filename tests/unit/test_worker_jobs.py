"""Unit tests for the worker job functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest

from document_viewer.worker.jobs import render_manifest, render_page

FIXTURE_PDF = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


@pytest.mark.asyncio
async def test_render_manifest_returns_payload() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    pdf = FIXTURE_PDF.read_bytes()

    pipeline = MagicMock()
    pipeline.manifest = AsyncMock(
        return_value=MagicMock(mime="application/pdf", pages=3, dims=[(595, 842)] * 3)
    )

    source = MagicMock()

    async def _fetch(key: str) -> tuple[Any, str]:
        async def _it() -> Any:
            yield pdf

        return _it(), "sha256:abc"

    source.fetch = AsyncMock(side_effect=_fetch)
    source.head = AsyncMock(return_value="sha256:abc")

    ctx = {
        "redis": redis,
        "pipeline": pipeline,
        "source": source,
        "settings": MagicMock(cache_ttl_seconds=900, allowed_mimes=["application/pdf"]),
    }
    out = await render_manifest(
        ctx, obj="kyc/x.pdf", sub="alice", case="c1", jti="j1", watermark_text="t"
    )
    assert out["pages"] == 3
    assert out["mime"] == "application/pdf"


@pytest.mark.asyncio
async def test_render_page_caches_after_first_render() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    pdf = FIXTURE_PDF.read_bytes()

    pipeline = MagicMock()
    pipeline.render_page = AsyncMock(return_value=b"RIFF\x00\x00\x00\x00WEBPVP8 ")

    source = MagicMock()

    async def _fetch(key: str) -> tuple[Any, str]:
        async def _it() -> Any:
            yield pdf

        return _it(), "sha256:abc"

    source.fetch = AsyncMock(side_effect=_fetch)
    source.head = AsyncMock(return_value="sha256:abc")

    ctx = {
        "redis": redis,
        "pipeline": pipeline,
        "source": source,
        "settings": MagicMock(cache_ttl_seconds=900, allowed_mimes=["application/pdf"]),
    }
    out1 = await render_page(
        ctx,
        obj="kyc/x.pdf",
        sub="alice",
        case="c1",
        jti="j1",
        page=1,
        width=800,
        watermark_text="t",
    )
    assert out1.startswith(b"RIFF")
    pipeline.render_page.reset_mock()
    out2 = await render_page(
        ctx,
        obj="kyc/x.pdf",
        sub="alice",
        case="c1",
        jti="j1",
        page=1,
        width=800,
        watermark_text="t",
    )
    pipeline.render_page.assert_not_awaited()
    assert out2 == out1
