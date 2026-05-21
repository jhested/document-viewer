"""Structured JSON logging on stdout for audit + observability."""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            structlog.processors.EventRenamer("event"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        cache_logger_on_first_use=True,
    )


class _Logger:
    def __init__(self, inner: structlog.stdlib.BoundLogger) -> None:
        self._inner = inner

    def info(self, event: str, /, **kwargs: Any) -> None:
        self._inner.info(event, **kwargs)

    def warning(self, event: str, /, **kwargs: Any) -> None:
        self._inner.warning(event, **kwargs)

    def error(self, event: str, /, **kwargs: Any) -> None:
        self._inner.error(event, **kwargs)

    @staticmethod
    def redact(text: str) -> str:
        return _JWT_PATTERN.sub("<jwt>", text)


def get_logger(name: str) -> _Logger:
    return _Logger(structlog.get_logger(name))
