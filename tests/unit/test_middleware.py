"""Unit tests for request-id middleware and error envelope."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from document_viewer.api.middleware import install_middleware


def _app() -> FastAPI:
    app = FastAPI()
    install_middleware(app)

    @app.get("/ok")
    def _ok() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/boom")
    def _boom() -> dict[str, str]:
        raise HTTPException(status_code=415, detail="bad mime")

    return app


def test_adds_request_id_header() -> None:
    r = TestClient(_app()).get("/ok")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")


def test_error_body_has_request_id() -> None:
    r = TestClient(_app()).get("/boom")
    assert r.status_code == 415
    body = r.json()
    assert body["error"] == "bad mime"
    assert body["request_id"]
