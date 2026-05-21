"""Unit tests for the /embed route."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from document_viewer.api.routes.embed import router


def test_embed_returns_html_with_main_js() -> None:
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).get("/embed/some-jwt")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("text/html")
    assert b"<!DOCTYPE html>" in r.content
    assert b"main.js" in r.content
