"""FastAPI application factory and `viewer-api` entrypoint."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from document_viewer.shared.logging import configure_logging


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(level="INFO")
    yield


def create_app() -> FastAPI:
    from document_viewer.api.routes import health

    app = FastAPI(title="document-viewer", lifespan=_lifespan)
    app.include_router(health.router)
    return app


app = create_app()


def main() -> None:
    """Console-script entry: `viewer-api`."""
    import uvicorn

    uvicorn.run(
        "document_viewer.api.app:app",
        host="0.0.0.0",  # noqa: S104  # binds all interfaces inside container
        port=8000,
        log_config=None,
    )
