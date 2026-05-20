"""Unit tests for the image pipeline (re-encode, EXIF strip, WebP encode)."""
from __future__ import annotations

import io

from PIL import Image

from document_viewer.render.image_pipeline import encode_webp, render_image
from document_viewer.shared.watermark import WatermarkConfig


def _pil_jpeg_with_exif() -> bytes:
    img = Image.new("RGB", (400, 300), "red")
    exif = img.getexif()
    exif[0x010F] = "ACME Camera"  # Make
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_render_image_strips_exif() -> None:
    raw = _pil_jpeg_with_exif()
    out = render_image(
        raw,
        mime="image/jpeg",
        width=300,
        watermark_text="t",
        watermark_config=WatermarkConfig(),
    )
    decoded = Image.open(io.BytesIO(out))
    decoded.load()
    assert not decoded.getexif() or 0x010F not in decoded.getexif()


def test_render_image_resizes_to_requested_width() -> None:
    img = Image.new("RGB", (4000, 3000), "blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    out = render_image(
        buf.getvalue(),
        mime="image/png",
        width=800,
        watermark_text="t",
        watermark_config=WatermarkConfig(),
    )
    decoded = Image.open(io.BytesIO(out))
    assert decoded.size[0] == 800


def test_encode_webp_round_trip() -> None:
    img = Image.new("RGB", (100, 100), "green")
    raw = encode_webp(img)
    decoded = Image.open(io.BytesIO(raw))
    assert decoded.format == "WEBP"
    assert decoded.size == (100, 100)
