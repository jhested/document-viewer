"""arq WorkerSettings + the `viewer-worker` entrypoint."""
from __future__ import annotations

from typing import ClassVar

from arq.connections import RedisSettings

from document_viewer.shared.config import Settings
from document_viewer.shared.logging import configure_logging


def _redis_settings(s: Settings) -> RedisSettings:
    return RedisSettings.from_dsn(s.redis_url)


class WorkerSettings:
    """Module-level config picked up by `arq document_viewer.worker.settings.WorkerSettings`."""

    functions: ClassVar[list[object]] = []  # populated below, after jobs loads

    @staticmethod
    def on_startup(ctx: dict[str, object]) -> None:
        configure_logging(level="INFO")


# Bind jobs lazily so this module imports cleanly even before T21's jobs.py
# lands; arq reads `WorkerSettings.functions` after import, by which time the
# `try`/`except ImportError` has either populated the list or left it empty
# (so a worker started against a missing-jobs module fails fast with a clear
# arq error rather than an opaque ImportError during module load).
try:
    from document_viewer.worker.jobs import (  # type: ignore[import-untyped]
        render_manifest,
        render_page,
    )

    WorkerSettings.functions = [render_manifest, render_page]
except ImportError:
    pass


def main() -> None:
    """Console-script entry: `viewer-worker`."""
    s = Settings()  # type: ignore[call-arg]  # fields loaded from env
    WorkerSettings.redis_settings = _redis_settings(s)  # type: ignore[attr-defined]
    WorkerSettings.max_jobs = s.worker_concurrency  # type: ignore[attr-defined]
    import asyncio

    from arq.worker import run_worker

    asyncio.run(run_worker(WorkerSettings))  # type: ignore[arg-type]


__all__ = ["WorkerSettings", "main"]
