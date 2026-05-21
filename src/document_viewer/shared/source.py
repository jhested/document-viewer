"""Source backend abstraction. FilesystemBackend for tests; S3Backend (T10) for prod."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

import aioboto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]


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


class S3Backend:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._session = aioboto3.Session(
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        self._endpoint = endpoint_url

    async def head(self, key: str) -> str:
        async with self._session.client("s3", endpoint_url=self._endpoint) as c:
            try:
                r = await c.head_object(Bucket=self._bucket, Key=key)
            except ClientError as e:
                if e.response["Error"]["Code"] in {"404", "NoSuchKey"}:
                    raise ObjectNotFound(key) from e
                raise
        return f"s3:{r['ETag'].strip('"')}"

    async def fetch(self, key: str) -> tuple[AsyncIterator[bytes], str]:
        etag = await self.head(key)

        async def _iter() -> AsyncIterator[bytes]:
            async with self._session.client("s3", endpoint_url=self._endpoint) as c:
                r = await c.get_object(Bucket=self._bucket, Key=key)
                async for chunk in r["Body"].iter_chunks(64 * 1024):
                    yield chunk

        return _iter(), etag
