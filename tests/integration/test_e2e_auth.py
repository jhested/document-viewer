"""End-to-end auth checks: expired, replayed, wrong issuer."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import jwt as pyjwt

# Must match the JWT_HMAC_SECRET configured for the api service in
# compose.test.yaml (>= 32 bytes to satisfy PyJWT key-length checks).
JWT_SECRET = os.getenv(
    "JWT_HMAC_SECRET",
    "test-secret-must-be-at-least-32-bytes-long!!",
)


def test_expired_token_401(client: httpx.Client) -> None:
    expired = pyjwt.encode(
        {
            "iss": "back-office",
            "sub": "x",
            "obj": "kyc/x.pdf",
            "case": "c",
            "jti": "j",
            "iat": int(time.time()) - 600,
            "exp": int(time.time()) - 60,
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    r = client.get(f"/render/{expired}/manifest")
    assert r.status_code == 401


def test_replayed_token_401(
    upload_fixture: Callable[[str, Path], None],
    make_token: Callable[..., str],
    client: httpx.Client,
) -> None:
    upload_fixture(
        "e2e/replay.pdf",
        Path(__file__).parent.parent / "fixtures" / "simple.pdf",
    )
    token = make_token("e2e/replay.pdf")
    r1 = client.get(f"/render/{token}/manifest")
    assert r1.status_code == 200
    r2 = client.get(f"/render/{token}/manifest")
    assert r2.status_code == 401


def test_wrong_iss_401(client: httpx.Client) -> None:
    bad = pyjwt.encode(
        {
            "iss": "evil",
            "sub": "x",
            "obj": "kyc/x.pdf",
            "case": "c",
            "jti": "j",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    r = client.get(f"/render/{bad}/manifest")
    assert r.status_code == 401
