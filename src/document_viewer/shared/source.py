"""Source backend abstraction. FilesystemBackend for tests; S3Backend (T10) for prod."""
from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol


class ObjectNotFound(Exception):
    """Object key does not exist in the backing store."""


class SourceBackend(Protocol):
    async def fetch(self, key: str) -> tuple[AsyncIterator[bytes], str]: ...
    async def head(self, key: str) -> str: ...


class FilesystemBackend:
    def __init__(self, *, root: str) -> None:
        self._root = Path(root).resolve()

    def _resolve(self, key: str) -> Path:
        target = (self._root / key).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as e:
            raise ObjectNotFound(key) from e
        if not target.is_file():
            raise ObjectNotFound(key)
        return target

    async def head(self, key: str) -> str:
        target = self._resolve(key)
        return _sha256_etag(target)

    async def fetch(self, key: str) -> tuple[AsyncIterator[bytes], str]:
        target = self._resolve(key)
        etag = _sha256_etag(target)

        async def _iter() -> AsyncIterator[bytes]:
            with target.open("rb") as f:
                while chunk := f.read(64 * 1024):
                    yield chunk

        return _iter(), etag


def _sha256_etag(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(64 * 1024):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"
