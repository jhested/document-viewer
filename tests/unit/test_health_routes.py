"""Unit tests for the health routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from document_viewer.api.routes.health import router


def test_healthz_returns_200() -> None:
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
