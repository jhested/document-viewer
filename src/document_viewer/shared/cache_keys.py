"""Deterministic cache key derivation. Every sensitive input must be in the key."""

from __future__ import annotations

import hashlib


def page_key(*, etag: str, sub: str, page: int, width: int) -> str:
    digest = hashlib.sha256(f"{etag}|{sub}|{page}|{width}".encode()).hexdigest()
    return f"page:{digest}"


def cleaned_pdf_key(*, etag: str, jti: str) -> str:
    digest = hashlib.sha256(f"{etag}|{jti}".encode()).hexdigest()
    return f"pdf-clean:{digest}"
