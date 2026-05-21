"""Async HTTP client for Gotenberg office->PDF conversion."""

from __future__ import annotations

import httpx


class GotenbergError(RuntimeError):
    pass


class GotenbergClient:
    def __init__(self, *, base_url: str, timeout_seconds: int) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def convert_to_pdf(self, *, filename: str, data: bytes) -> bytes:
        files = {"files": (filename, data, "application/octet-stream")}
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(f"{self._base}/forms/libreoffice/convert", files=files)
        if r.status_code != 200:
            raise GotenbergError(f"gotenberg returned {r.status_code}")
        return r.content
