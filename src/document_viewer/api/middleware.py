"""HTTP middleware: request IDs, uniform error envelope."""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from document_viewer.shared.errors import RateLimitExceeded, RenderError, error_to_http_status
from document_viewer.shared.logging import get_logger

_log = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = rid
        return resp


def _error_response(rid: str, status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": message, "request_id": rid},
        headers={"X-Request-ID": rid, "Cache-Control": "no-store"},
    )


def install_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(HTTPException)
    async def _http_exc(request: Request, exc: HTTPException) -> Response:
        rid = getattr(request.state, "request_id", "")
        return _error_response(rid, exc.status_code, exc.detail)

    @app.exception_handler(RenderError)
    async def _render_exc(request: Request, exc: RenderError) -> Response:
        rid = getattr(request.state, "request_id", "")
        resp = _error_response(rid, error_to_http_status(exc), exc.safe_message)
        if isinstance(exc, RateLimitExceeded):
            resp.headers["Retry-After"] = str(exc.retry_after)
        return resp

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> Response:
        rid = getattr(request.state, "request_id", "")
        _log.error(
            "unhandled_exception",
            request_id=rid,
            path=str(request.url.path),
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return _error_response(rid, 500, "internal error")
