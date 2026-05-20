"""Unit tests for the /render routes."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from document_viewer.api.deps import (
    get_arq_pool,
    get_jwt_verifier,
    get_replay_guard,
    get_settings,
)
from document_viewer.api.routes.render import router
from document_viewer.shared.config import Settings
from document_viewer.shared.jwt_auth import JwtVerifier

SECRET = "test-secret-must-be-at-least-32-bytes-long!!"


def _token(**overrides: object) -> str:
    payload: dict[str, object] = {
        "iss": "back-office",
        "sub": "alice@bank.com",
        "obj": "kyc/case-123/passport.pdf",
        "case": "case-123",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
        "jti": "uuid-1",
    }
    payload.update(overrides)
    return pyjwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)

    settings = Settings(
        jwt_algorithm="HS256",
        jwt_hmac_secret=SECRET,  # type: ignore[arg-type]  # pydantic coerces to SecretStr
        redis_url="redis://x",
        source_backend="fs",
        jwt_required_iss="back-office",
    )
    arq = MagicMock()
    manifest_payload = {
        "mime": "application/pdf",
        "pages": 3,
        "dims": [{"w": 595, "h": 842}] * 3,
        "etag": "sha256:abc",
    }
    arq.enqueue_job = AsyncMock(
        return_value=MagicMock(result=AsyncMock(return_value=manifest_payload))
    )
    replay = MagicMock()
    replay.claim = AsyncMock(return_value=None)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_jwt_verifier] = lambda: JwtVerifier(
        algorithm="HS256", hmac_secret=SECRET, required_iss="back-office"
    )
    app.dependency_overrides[get_arq_pool] = lambda: arq
    app.dependency_overrides[get_replay_guard] = lambda: replay
    return TestClient(app)


def test_manifest_returns_200_and_no_store(client: TestClient) -> None:
    r = client.get(f"/render/{_token()}/manifest")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-store"
    assert r.json()["pages"] == 3


def test_manifest_rejects_bad_jwt(client: TestClient) -> None:
    r = client.get("/render/not-a-jwt/manifest")
    assert r.status_code == 401
