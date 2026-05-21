"""Per-jti rate limit unit tests."""
from __future__ import annotations

import fakeredis.aioredis
import pytest

from document_viewer.shared.errors import RateLimitExceeded
from document_viewer.shared.ratelimit import JtiRateLimiter


@pytest.mark.asyncio
async def test_disabled_when_limit_zero() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    limiter = JtiRateLimiter(redis, limit=0, window_seconds=60)
    assert not limiter.enabled
    for _ in range(10):
        await limiter.check("jti-1")
    assert await redis.get("rl:jti:jti-1") is None


@pytest.mark.asyncio
async def test_allows_up_to_limit_then_blocks() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    limiter = JtiRateLimiter(redis, limit=3, window_seconds=60)
    for _ in range(3):
        await limiter.check("jti-1")
    with pytest.raises(RateLimitExceeded) as ei:
        await limiter.check("jti-1")
    assert ei.value.retry_after >= 1


@pytest.mark.asyncio
async def test_different_jtis_have_independent_buckets() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    limiter = JtiRateLimiter(redis, limit=2, window_seconds=60)
    await limiter.check("jti-a")
    await limiter.check("jti-a")
    await limiter.check("jti-b")
    await limiter.check("jti-b")
    with pytest.raises(RateLimitExceeded):
        await limiter.check("jti-a")
    with pytest.raises(RateLimitExceeded):
        await limiter.check("jti-b")


@pytest.mark.asyncio
async def test_ttl_set_on_first_increment() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    limiter = JtiRateLimiter(redis, limit=5, window_seconds=42)
    await limiter.check("jti-x")
    ttl = await redis.ttl("rl:jti:jti-x")
    assert 35 <= ttl <= 42
