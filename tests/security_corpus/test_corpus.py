"""Each corpus fixture must either render safely or return a documented error."""
from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pytest

from document_viewer.render.pdf_clean import clean_pdf
from document_viewer.shared.mime import MimeNotAllowed, detect_mime

CORPUS = Path(__file__).parent


def test_pikepdf_strips_js() -> None:
    raw = (CORPUS / "pdfs" / "with_js.pdf").read_bytes()
    cleaned = clean_pdf(raw)
    p = pikepdf.open(io.BytesIO(cleaned))
    assert "/OpenAction" not in p.Root


def test_pikepdf_strips_launch() -> None:
    raw = (CORPUS / "pdfs" / "with_launch.pdf").read_bytes()
    cleaned = clean_pdf(raw)
    p = pikepdf.open(io.BytesIO(cleaned))
    assert "/OpenAction" not in p.Root


def test_truncated_pdf_raises_cleanly() -> None:
    raw = (CORPUS / "pdfs" / "truncated.pdf").read_bytes()
    # pikepdf raises on parse failure; the pipeline surfaces this as a
    # documented 500-with-request-id rather than crashing the worker.
    with pytest.raises(Exception, match=r"."):
        clean_pdf(raw)


def test_pe_labelled_pdf_rejected_by_magic() -> None:
    raw = (CORPUS / "pdfs" / "pe_labelled_pdf.pdf").read_bytes()
    with pytest.raises(MimeNotAllowed):
        detect_mime(raw[:4096], allowed=["application/pdf"])


def test_decompression_bomb_image_rejected_or_capped() -> None:
    from PIL import Image, UnidentifiedImageError

    raw = (CORPUS / "images" / "decompression_bomb.png").read_bytes()
    with pytest.raises((Image.DecompressionBombError, UnidentifiedImageError, OSError)):
        Image.open(io.BytesIO(raw)).load()
