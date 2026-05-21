"""arq WorkerSettings + the `viewer-worker` entrypoint."""
from __future__ import annotations

from typing import Any, ClassVar

from arq.connections import RedisSettings

from document_viewer.render.gotenberg_client import GotenbergClient
from document_viewer.render.pipeline import RenderPipeline
from document_viewer.shared.config import Settings
from document_viewer.shared.logging import configure_logging
from document_viewer.shared.source import (
    FilesystemBackend,
    S3Backend,
    SourceBackend,
)
from document_viewer.shared.watermark import WatermarkConfig


def _redis_settings(s: Settings) -> RedisSettings:
    return RedisSettings.from_dsn(s.redis_url)


def _build_source(s: Settings) -> SourceBackend:
    if s.source_backend == "fs":
        return FilesystemBackend(root=s.fs_root)
    return S3Backend(
        bucket=s.s3_bucket or "",
        region=s.s3_region,
        endpoint_url=s.s3_endpoint,
        access_key_id=(
            s.s3_access_key_id.get_secret_value() if s.s3_access_key_id else None
        ),
        secret_access_key=(
            s.s3_secret_access_key.get_secret_value()
            if s.s3_secret_access_key
            else None
        ),
    )


class WorkerSettings:
    """Module-level config picked up by `arq document_viewer.worker.settings.WorkerSettings`."""

    functions: ClassVar[list[object]] = []  # populated below, after jobs loads
    # arq's default is 0.5s; for an HTTP-blocking request path that dispatch
    # latency dominates real work on small docs and masks cache speedups.
    poll_delay: ClassVar[float] = 0.1

    @staticmethod
    async def on_startup(ctx: dict[str, Any]) -> None:
        configure_logging(level="INFO")
        # Job functions read settings/source/pipeline from ctx; arq itself only
        # provides ctx["redis"] (the queue pool, which we also reuse as cache).
        s = Settings()  # type: ignore[call-arg]  # fields loaded from env
        ctx["settings"] = s
        ctx["source"] = _build_source(s)
        ctx["pipeline"] = RenderPipeline(
            gotenberg=GotenbergClient(
                base_url=s.gotenberg_url,
                timeout_seconds=s.office_timeout_seconds,
            ),
            settings=s,
            watermark=WatermarkConfig(
                opacity=s.watermark_opacity,
                font_size=s.watermark_font_size,
                angle=s.watermark_angle,
            ),
        )


# Bind jobs lazily so this module imports cleanly even before T21's jobs.py
# lands; arq reads `WorkerSettings.functions` after import, by which time the
# `try`/`except ImportError` has either populated the list or left it empty
# (so a worker started against a missing-jobs module fails fast with a clear
# arq error rather than an opaque ImportError during module load).
try:
    from document_viewer.worker.jobs import render_manifest, render_page

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
