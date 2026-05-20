"""Unit tests for the error taxonomy."""
from __future__ import annotations

from document_viewer.shared.errors import (
    ObjectTooLarge,
    PageOutOfRange,
    RenderError,
    RenderTimeout,
    UnsupportedMime,
    error_to_http_status,
)


def test_status_mapping() -> None:
    assert error_to_http_status(ObjectTooLarge("100mb")) == 413
    assert error_to_http_status(PageOutOfRange(5)) == 404
    assert error_to_http_status(UnsupportedMime("application/x-msi")) == 415
    assert error_to_http_status(RenderTimeout("page 3")) == 504
    assert error_to_http_status(RenderError("worker crashed")) == 500


def test_render_error_carries_safe_message() -> None:
    e = RenderError("worker crashed")
    assert "worker crashed" in e.safe_message
    # Never echoes source bytes
    assert "%PDF" not in e.safe_message
