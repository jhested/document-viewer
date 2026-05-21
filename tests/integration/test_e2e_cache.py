"""End-to-end: page renders are cached in Redis by etag/sub/page/width."""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import boto3
import httpx
import redis as redis_sync

from document_viewer.shared.cache_keys import page_key

FIXTURE = Path(__file__).parent.parent / "fixtures" / "simple.pdf"

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6381/0")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_KEY = os.getenv("S3_ACCESS_KEY_ID", "minio-user")
S3_SECRET = os.getenv("S3_SECRET_ACCESS_KEY", "minio-password")
BUCKET = os.getenv("S3_BUCKET", "kyc-docs")


def _s3_etag(key: str) -> str:
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_KEY,
        aws_secret_access_key=S3_SECRET,
    )
    return s3.head_object(Bucket=BUCKET, Key=key)["ETag"].strip('"')


def test_second_page_request_is_cached(
    upload_fixture: Callable[[str, Path], None],
    make_token: Callable[..., str],
    client: httpx.Client,
) -> None:
    key = "e2e/cache.pdf"
    upload_fixture(key, FIXTURE)

    t1 = make_token(key, sub="alice")
    t2 = make_token(key, sub="alice")

    r1 = client.get(f"/render/{t1}/page/1?w=800")
    assert r1.status_code == 200

    # The S3 backend uses "s3:<etag>" as its source etag; the cache key derives
    # from (etag, sub, page, width). After r1, the cached webp must be present.
    redis = redis_sync.Redis.from_url(REDIS_URL)
    expected_key = page_key(
        etag=f"s3:{_s3_etag(key)}", sub="alice", page=1, width=800
    )
    cached = redis.get(expected_key)
    assert cached is not None, f"page cache miss for key {expected_key}"
    assert cached == r1.content

    # Second request returns the same bytes (cache hit produces identical output).
    r2 = client.get(f"/render/{t2}/page/1?w=800")
    assert r2.status_code == 200
    assert r2.content == r1.content
