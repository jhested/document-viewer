"""Unit tests for cache key derivation."""
from __future__ import annotations

from document_viewer.shared.cache_keys import cleaned_pdf_key, page_key


def test_page_key_is_deterministic() -> None:
    a = page_key(etag="sha256:abc", sub="alice", page=3, width=1200)
    b = page_key(etag="sha256:abc", sub="alice", page=3, width=1200)
    assert a == b
    assert a.startswith("page:")


def test_page_key_changes_with_any_input() -> None:
    base = page_key(etag="sha256:abc", sub="alice", page=3, width=1200)
    assert base != page_key(etag="sha256:abc", sub="alice", page=3, width=1201)
    assert base != page_key(etag="sha256:abc", sub="alice", page=4, width=1200)
    assert base != page_key(etag="sha256:abc", sub="bob", page=3, width=1200)
    assert base != page_key(etag="sha256:other", sub="alice", page=3, width=1200)


def test_cleaned_pdf_key_uses_jti() -> None:
    a = cleaned_pdf_key(etag="sha256:abc", jti="uuid-1")
    b = cleaned_pdf_key(etag="sha256:abc", jti="uuid-2")
    assert a != b
    assert a.startswith("pdf-clean:")
