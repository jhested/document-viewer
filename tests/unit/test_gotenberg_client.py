"""Unit tests for the Gotenberg HTTP client."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from document_viewer.render.gotenberg_client import GotenbergClient, GotenbergError


@pytest.mark.asyncio
async def test_convert_returns_pdf_bytes(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://gotenberg:3000/forms/libreoffice/convert",
        content=b"%PDF-1.7 produced",
        headers={"Content-Type": "application/pdf"},
    )
    client = GotenbergClient(base_url="http://gotenberg:3000", timeout_seconds=60)
    pdf = await client.convert_to_pdf(filename="x.docx", data=b"docx-bytes")
    assert pdf == b"%PDF-1.7 produced"


@pytest.mark.asyncio
async def test_convert_raises_on_500(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://gotenberg:3000/forms/libreoffice/convert",
        status_code=500,
    )
    client = GotenbergClient(base_url="http://gotenberg:3000", timeout_seconds=60)
    with pytest.raises(GotenbergError):
        await client.convert_to_pdf(filename="x.docx", data=b"x")
