"""Per-jti soft rate limit backed by Redis.

This is the application-side backstop. Ingress-level limits (per IP, per
zero-trust identity) remain the primary control; see
`docs/security/hardening.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from document_viewer.shared.errors import RateLimitExceeded

if TYPE_CHECKING:
    from redis.asyncio import Redis


class JtiRateLimiter:
    """Fixed-window counter per JWT `jti`.

    A `limit <= 0` disables enforcement entirely — useful for dev environments
    or test fixtures where the cap would otherwise be a flake source.
    """

    def __init__(
        self,
        redis: Redis,  # type: ignore[type-arg]
        *,
        limit: int,
        window_seconds: int,
    ) -> None:
        self._redis = redis
        self._limit = limit
        self._window = window_seconds

    @property
    def enabled(self) -> bool:
        return self._limit > 0

    async def check(self, jti: str) -> None:
        if not self.enabled:
            return
        key = f"rl:jti:{jti}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, self._window)
        if count > self._limit:
            ttl = await self._redis.ttl(key)
            raise RateLimitExceeded(retry_after=max(int(ttl), 1))
