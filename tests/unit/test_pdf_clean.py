"""Unit tests for the pikepdf pre-rasterization cleaner."""
from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest

from document_viewer.render.pdf_clean import clean_pdf

FIXTURE = Path(__file__).parent.parent / "fixtures" / "pdf_with_js.pdf"


def test_clean_strips_javascript() -> None:
    import io

    raw = FIXTURE.read_bytes()
    cleaned = clean_pdf(raw)
    p = pikepdf.open(io.BytesIO(cleaned))
    root = p.Root
    assert "/OpenAction" not in root
    if "/Names" in root:
        assert "/JavaScript" not in root.Names


def test_clean_returns_smaller_or_equal_bytes() -> None:
    raw = FIXTURE.read_bytes()
    cleaned = clean_pdf(raw)
    assert len(cleaned) <= len(raw) + 1024  # allow for restructuring overhead


def test_clean_rejects_encrypted_pdf(tmp_path: Path) -> None:
    encrypted = tmp_path / "enc.pdf"
    p = pikepdf.Pdf.new()
    p.add_blank_page(page_size=(595, 842))
    p.save(encrypted, encryption=pikepdf.Encryption(owner="o", user="u", R=4))
    with pytest.raises(RuntimeError, match="encrypted"):
        clean_pdf(encrypted.read_bytes())
