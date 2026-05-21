"""FastAPI dependency providers - Settings, Redis pool, JWT verifier, arq pool."""

from __future__ import annotations

from functools import lru_cache

import redis.asyncio as redis_async
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from document_viewer.shared.config import Settings
from document_viewer.shared.jwt_auth import JwtReplayGuard, JwtVerifier
from document_viewer.shared.ratelimit import JtiRateLimiter


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # fields loaded from env


@lru_cache(maxsize=1)
def get_jwt_verifier() -> JwtVerifier:
    s = get_settings()
    return JwtVerifier(
        algorithm=s.jwt_algorithm,
        hmac_secret=s.jwt_hmac_secret.get_secret_value() or None,
        public_key=s.jwt_public_key.get_secret_value() or None,
        required_iss=s.jwt_required_iss,
    )


async def get_redis() -> redis_async.Redis:  # type: ignore[type-arg]
    s = get_settings()
    return redis_async.from_url(s.redis_url, decode_responses=False)


async def get_arq_pool() -> ArqRedis:
    s = get_settings()
    return await create_pool(RedisSettings.from_dsn(s.redis_url))


async def get_replay_guard() -> JwtReplayGuard:
    redis = await get_redis()
    return JwtReplayGuard(redis)


async def get_rate_limiter() -> JtiRateLimiter:
    s = get_settings()
    redis = await get_redis()
    return JtiRateLimiter(
        redis,
        limit=s.rate_limit_per_jti,
        window_seconds=s.rate_limit_window_seconds,
    )
