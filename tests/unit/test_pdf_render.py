"""Unit tests for pypdfium2 PDF rendering."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from document_viewer.render.pdf_render import PdfDocument, render_page
from document_viewer.shared.errors import PageOutOfRange

FIXTURE = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


def test_open_returns_page_count_and_dims() -> None:
    with PdfDocument.from_bytes(FIXTURE.read_bytes()) as doc:
        assert doc.page_count == 3
        dims = doc.page_dims()
        assert len(dims) == 3
        for w, h in dims:
            assert w > 0 and h > 0


def test_render_page_produces_image_at_requested_width() -> None:
    with PdfDocument.from_bytes(FIXTURE.read_bytes()) as doc:
        img = render_page(doc, page_index=0, width=1200)
        assert isinstance(img, Image.Image)
        assert 1198 <= img.size[0] <= 1202  # ±1px tolerance


def test_render_page_out_of_range_raises() -> None:
    with (
        PdfDocument.from_bytes(FIXTURE.read_bytes()) as doc,
        pytest.raises(PageOutOfRange),
    ):
        render_page(doc, page_index=99, width=1200)


def test_dpi_is_capped_for_huge_requested_widths() -> None:
    with PdfDocument.from_bytes(FIXTURE.read_bytes()) as doc:
        img = render_page(doc, page_index=0, width=20000, max_dpi=300)
        # 8.5in x 300dpi = 2550 px
        assert img.size[0] <= 2600
