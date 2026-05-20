"""Liveness and readiness endpoints."""
from __future__ import annotations

from typing import Annotated

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends

from document_viewer.api.deps import get_redis

router = APIRouter()

RedisDep = Annotated[redis_async.Redis, Depends(get_redis)]


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(redis: RedisDep) -> dict[str, str]:  # type: ignore[type-arg]
    pong = await redis.ping()
    return {"status": "ok" if pong else "degraded"}
