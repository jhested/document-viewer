"""Server-side watermark rendering, baked into image pixels."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class WatermarkConfig:
    opacity: float = 0.18
    font_size: int = 24
    angle: float = -30.0
    color: tuple[int, int, int] = (128, 128, 128)
    tile_h: int = 350  # vertical spacing between tiled watermarks


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default(size=size)


def apply_watermark(src: Image.Image, *, text: str, config: WatermarkConfig) -> Image.Image:
    base = src.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))

    # Build a single rotated text tile
    font = _load_font(config.font_size)
    bbox = font.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 16
    tile = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    alpha = max(1, min(255, int(255 * config.opacity)))
    ImageDraw.Draw(tile).text((pad, pad), text, fill=(*config.color, alpha), font=font)
    rotated = tile.rotate(config.angle, resample=Image.BICUBIC, expand=True)

    # Tile over the image
    rw, rh = rotated.size
    y = -rh // 2
    row = 0
    while y < base.size[1]:
        x_offset = (rw // 2) if row % 2 else 0
        x = -rw // 2 + x_offset
        while x < base.size[0]:
            overlay.alpha_composite(rotated, (x, y))
            x += rw
        y += int(config.tile_h * math.cos(math.radians(config.angle)))
        row += 1

    return Image.alpha_composite(base, overlay).convert("RGB")
