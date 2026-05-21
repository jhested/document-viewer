"""Integration fixtures. Assumes compose.test.yaml is already up.

All tests in this directory are auto-marked `integration` and skipped by the
default `pytest` invocation. Run them with:

    docker compose -f compose.test.yaml up -d --wait
    pytest -m integration tests/integration
"""
from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import boto3
import httpx
import jwt as pyjwt
import pytest


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Auto-tag every test in this package with the `integration` marker.

    pyproject's `addopts = "-m 'not integration'"` then skips them by default;
    enable with `pytest -m integration tests/integration`.
    """
    for item in items:
        if "tests/integration" in str(item.path):
            item.add_marker(pytest.mark.integration)

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_KEY = os.getenv("S3_ACCESS_KEY_ID", "minio-user")
S3_SECRET = os.getenv("S3_SECRET_ACCESS_KEY", "minio-password")
BUCKET = os.getenv("S3_BUCKET", "kyc-docs")
JWT_SECRET = os.getenv(
    "JWT_HMAC_SECRET",
    "test-secret-must-be-at-least-32-bytes-long!!",
)


@pytest.fixture(scope="session", autouse=True)
def _ensure_bucket() -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_KEY,
        aws_secret_access_key=S3_SECRET,
    )
    try:
        s3.head_bucket(Bucket=BUCKET)
    except Exception:
        s3.create_bucket(Bucket=BUCKET)


@pytest.fixture
def upload_fixture() -> Callable[[str, Path], None]:
    def _u(key: str, src: Path) -> None:
        s3 = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_KEY,
            aws_secret_access_key=S3_SECRET,
        )
        s3.put_object(Bucket=BUCKET, Key=key, Body=src.read_bytes())

    return _u


@pytest.fixture
def make_token() -> Callable[..., str]:
    def _t(
        obj: str,
        *,
        sub: str = "alice@bank.com",
        case: str = "case-1",
        ttl: int = 60,
    ) -> str:
        return pyjwt.encode(
            {
                "iss": "back-office",
                "sub": sub,
                "obj": obj,
                "case": case,
                "iat": int(time.time()),
                "exp": int(time.time()) + ttl,
                "jti": uuid.uuid4().hex,
            },
            JWT_SECRET,
            algorithm="HS256",
        )

    return _t


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=API_BASE, timeout=60) as c:
        yield c
