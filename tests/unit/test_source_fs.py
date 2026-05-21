"""Unit tests for the filesystem source backend."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_viewer.shared.source import FilesystemBackend, ObjectNotFound


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "kyc").mkdir()
    (tmp_path / "kyc" / "passport.pdf").write_bytes(b"%PDF-1.7\n...payload...")
    return tmp_path


@pytest.mark.asyncio
async def test_fetch_returns_bytes_and_etag(root: Path) -> None:
    be = FilesystemBackend(root=str(root))
    chunks, etag = await be.fetch("kyc/passport.pdf")
    body = b""
    async for c in chunks:
        body += c
    assert body.startswith(b"%PDF-1.7")
    assert etag.startswith("sha256:")


@pytest.mark.asyncio
async def test_head_returns_etag(root: Path) -> None:
    be = FilesystemBackend(root=str(root))
    etag = await be.head("kyc/passport.pdf")
    assert etag.startswith("sha256:")


@pytest.mark.asyncio
async def test_fetch_raises_for_missing(root: Path) -> None:
    be = FilesystemBackend(root=str(root))
    with pytest.raises(ObjectNotFound):
        await be.fetch("kyc/missing.pdf")


@pytest.mark.asyncio
async def test_rejects_path_traversal(root: Path) -> None:
    be = FilesystemBackend(root=str(root))
    with pytest.raises(ObjectNotFound):
        await be.fetch("../etc/passwd")
