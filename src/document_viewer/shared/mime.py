"""Magic-byte mime detection. Extension is never trusted."""

from __future__ import annotations

import magic


class MimeNotAllowed(Exception):
    """Detected mime is not in the configured allowlist."""

    def __init__(self, detected: str) -> None:
        super().__init__(f"detected mime not allowed: {detected}")
        self.detected = detected


_magic = magic.Magic(mime=True)


def detect_mime(head: bytes, *, allowed: list[str]) -> str:
    """Return the detected mime if it's in allowed; raise MimeNotAllowed otherwise."""
    detected = _magic.from_buffer(head)
    if detected not in allowed:
        raise MimeNotAllowed(detected)
    return detected
