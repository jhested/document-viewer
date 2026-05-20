"""Unit tests for the S3 source backend, using moto."""
from __future__ import annotations

import boto3
import pytest
from moto import mock_aws  # type: ignore[import-untyped]

from document_viewer.shared.source import ObjectNotFound, S3Backend


@pytest.mark.asyncio
async def test_fetch_streams_bytes_and_returns_etag() -> None:
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="kyc-docs")
        boto3.client("s3", region_name="us-east-1").put_object(
            Bucket="kyc-docs", Key="case-1/passport.pdf", Body=b"%PDF-1.7 hello"
        )

        be = S3Backend(bucket="kyc-docs", region="us-east-1", endpoint_url=None)
        chunks, etag = await be.fetch("case-1/passport.pdf")
        body = b""
        async for c in chunks:
            body += c
        assert body == b"%PDF-1.7 hello"
        assert etag.startswith("s3:")


@pytest.mark.asyncio
async def test_fetch_missing_raises() -> None:
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="kyc-docs")
        be = S3Backend(bucket="kyc-docs", region="us-east-1", endpoint_url=None)
        with pytest.raises(ObjectNotFound):
            await be.fetch("missing.pdf")
