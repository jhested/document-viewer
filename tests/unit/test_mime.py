"""Unit tests for magic-byte mime detection."""

from __future__ import annotations

import pytest

from document_viewer.shared.mime import MimeNotAllowed, detect_mime

PDF_HEADER = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
PNG_HEADER = (
    b"\x89PNG\r\n\x1a\n"  # signature
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"  # IHDR chunk header
    b"\x08\x02\x00\x00\x00\x90wS\xde"  # IHDR data + CRC
)
DOCX_HEADER = b"PK\x03\x04\x14\x00\x06\x00"
PE_HEADER = b"MZ\x90\x00"


def test_detects_pdf() -> None:
    assert detect_mime(PDF_HEADER, allowed=["application/pdf"]) == "application/pdf"


def test_detects_png() -> None:
    assert detect_mime(PNG_HEADER, allowed=["image/png", "application/pdf"]) == "image/png"


def test_rejects_disallowed_mime() -> None:
    with pytest.raises(MimeNotAllowed):
        detect_mime(PE_HEADER, allowed=["application/pdf"])


def test_ignores_extension_in_input() -> None:
    """Function takes bytes only — there's no way to spoof via filename."""
    with pytest.raises(MimeNotAllowed):
        detect_mime(PE_HEADER, allowed=["application/pdf"])
