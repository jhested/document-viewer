"""Image source pipeline: open -> strip metadata -> resize -> watermark -> WebP."""
from __future__ import annotations

import io

from PIL import Image

from document_viewer.shared.watermark import WatermarkConfig, apply_watermark

# Re-register HEIC support if pillow-heif is installed
try:
    import pillow_heif  # type: ignore[import-untyped]

    pillow_heif.register_heif_opener()
except ImportError:
    pass

Image.MAX_IMAGE_PIXELS = 200_000_000  # ~200 MP guard against decompression bombs


def encode_webp(img: Image.Image, *, quality: int = 82, method: int = 4) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=method)
    return buf.getvalue()


def render_image(
    data: bytes,
    *,
    mime: str,
    width: int,
    watermark_text: str,
    watermark_config: WatermarkConfig,
) -> bytes:
    src = Image.open(io.BytesIO(data))
    src.load()
    # Drop EXIF / metadata by recreating the image
    cleaned = Image.new(src.mode, src.size)
    cleaned.paste(src)
    # Resize maintaining aspect
    if cleaned.size[0] != width:
        h = round(cleaned.size[1] * (width / cleaned.size[0]))
        cleaned = cleaned.resize((width, h), Image.LANCZOS)
    if cleaned.mode != "RGB":
        cleaned = cleaned.convert("RGB")
    watermarked = apply_watermark(cleaned, text=watermark_text, config=watermark_config)
    return encode_webp(watermarked)
