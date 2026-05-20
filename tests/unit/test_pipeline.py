"""Unit tests for the pipeline dispatcher."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from document_viewer.render.pipeline import RenderJob, RenderPipeline
from document_viewer.shared.watermark import WatermarkConfig

FIXTURE_PDF = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


@dataclass
class _DummySettings:
    max_page_width: int = 2400
    watermark_opacity: float = 0.18
    watermark_font_size: int = 24
    watermark_angle: float = -30.0
    watermark_color: str = "#808080"
    office_timeout_seconds: int = 60


@pytest.fixture
def watermark_cfg() -> WatermarkConfig:
    return WatermarkConfig()


@pytest.mark.asyncio
async def test_pdf_pipeline_returns_manifest_and_page(watermark_cfg: WatermarkConfig) -> None:
    pdf_bytes = FIXTURE_PDF.read_bytes()
    pipeline = RenderPipeline(
        gotenberg=MagicMock(),
        settings=_DummySettings(),
        watermark=watermark_cfg,
    )

    job = RenderJob(
        source_bytes=pdf_bytes,
        mime="application/pdf",
        watermark_text="alice",
    )
    manifest = await pipeline.manifest(job)
    assert manifest.pages == 3
    assert len(manifest.dims) == 3

    page = await pipeline.render_page(job, page=1, width=800)
    assert page.startswith(b"RIFF") and b"WEBP" in page[:16]


@pytest.mark.asyncio
async def test_docx_pipeline_calls_gotenberg(watermark_cfg: WatermarkConfig) -> None:
    pdf_bytes = FIXTURE_PDF.read_bytes()
    gotenberg = MagicMock()
    gotenberg.convert_to_pdf = AsyncMock(return_value=pdf_bytes)

    pipeline = RenderPipeline(
        gotenberg=gotenberg,
        settings=_DummySettings(),
        watermark=watermark_cfg,
    )
    job = RenderJob(
        source_bytes=b"docx-bytes",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        watermark_text="alice",
    )
    manifest = await pipeline.manifest(job)
    assert manifest.pages == 3
    gotenberg.convert_to_pdf.assert_awaited_once()
