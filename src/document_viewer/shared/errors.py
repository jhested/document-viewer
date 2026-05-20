"""Domain error taxonomy. Each maps to a stable HTTP status."""
from __future__ import annotations


class RenderError(Exception):
    """Generic render failure. Carries only operator-safe info, never source bytes."""

    @property
    def safe_message(self) -> str:
        return str(self)


class RenderTimeout(RenderError):
    pass


class ObjectTooLarge(RenderError):
    pass


class PageOutOfRange(RenderError):
    pass


class UnsupportedMime(RenderError):
    pass


def error_to_http_status(e: RenderError) -> int:
    if isinstance(e, ObjectTooLarge):
        return 413
    if isinstance(e, PageOutOfRange):
        return 404
    if isinstance(e, UnsupportedMime):
        return 415
    if isinstance(e, RenderTimeout):
        return 504
    return 500
