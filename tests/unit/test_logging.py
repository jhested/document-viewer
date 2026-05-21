"""Unit tests for structured logging."""

from __future__ import annotations

import json

import pytest

from document_viewer.shared.logging import configure_logging, get_logger


def test_logger_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO")
    log = get_logger("test")

    log.info("page_rendered", request_id="abc", sub="alice", page=3, render_ms=145)

    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert payload["event"] == "page_rendered"
    assert payload["request_id"] == "abc"
    assert payload["sub"] == "alice"
    assert payload["page"] == 3
    assert payload["render_ms"] == 145
    assert "timestamp" in payload
    assert payload["level"] == "info"


def test_logger_redacts_jwt_in_message() -> None:
    configure_logging(level="INFO")
    log = get_logger("test")

    redacted = log.redact("path=/render/eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.sig/page/1")
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted
    assert "<jwt>" in redacted
