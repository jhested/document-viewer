"""Unit tests for the config module."""
from __future__ import annotations

import pytest

from document_viewer.shared.config import Settings


def test_settings_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SOURCE_BACKEND", "fs")
    monkeypatch.setenv("FS_ROOT", "/tmp/docs")  # noqa: S108

    s = Settings()

    assert s.jwt_algorithm == "HS256"
    assert s.jwt_hmac_secret.get_secret_value() == "test-secret"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.source_backend == "fs"


def test_settings_defaults() -> None:
    s = Settings(
        jwt_algorithm="HS256",
        jwt_hmac_secret="x",
        redis_url="redis://x",
        source_backend="fs",
    )
    assert s.max_source_bytes == 100 * 1024 * 1024
    assert s.max_pages == 500
    assert s.max_page_width == 2400
    assert s.cache_ttl_seconds == 900


def test_settings_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError):
        Settings(
            jwt_algorithm="HS256",
            jwt_hmac_secret="x",
            redis_url="redis://x",
            source_backend="ftp",
        )
