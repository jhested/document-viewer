"""Unit tests for watermark rendering."""

from __future__ import annotations

from PIL import Image

from document_viewer.shared.watermark import WatermarkConfig, apply_watermark


def test_apply_watermark_returns_image_of_same_size() -> None:
    src = Image.new("RGB", (800, 1000), "white")
    cfg = WatermarkConfig()
    out = apply_watermark(src, text="alice · case-123 · 2026-05-20T14:30Z", config=cfg)
    assert out.size == src.size


def test_apply_watermark_changes_pixels() -> None:
    """The watermark must visibly modify the source pixels."""
    src = Image.new("RGB", (800, 1000), "white")
    out = apply_watermark(src, text="alice", config=WatermarkConfig())
    # Compare a sample band that should overlap a tiled watermark instance
    src_pixels = src.crop((100, 400, 700, 600)).tobytes()
    out_pixels = out.crop((100, 400, 700, 600)).tobytes()
    assert src_pixels != out_pixels


def test_apply_watermark_tiles_so_cropping_leaves_instances() -> None:
    """At least 3 visually distinct watermark bands should be present in a tall image."""
    src = Image.new("RGB", (800, 1600), "white")
    out = apply_watermark(src, text="alice", config=WatermarkConfig())
    bands = [
        out.crop((0, 0, 800, 400)).tobytes(),
        out.crop((0, 400, 800, 800)).tobytes(),
        out.crop((0, 800, 800, 1200)).tobytes(),
        out.crop((0, 1200, 800, 1600)).tobytes(),
    ]
    untouched = Image.new("RGB", (800, 400), "white").tobytes()
    changed = [b for b in bands if b != untouched]
    assert len(changed) >= 3
