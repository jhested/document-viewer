"""Shared pytest fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip viewer-related env vars before each test."""
    import os
    for k in list(os.environ):
        if k.startswith((
            "JWT_", "S3_", "REDIS_", "MAX_", "CACHE_",
            "WATERMARK_", "GOTENBERG_", "SOURCE_", "FS_",
        )):
            monkeypatch.delenv(k, raising=False)
