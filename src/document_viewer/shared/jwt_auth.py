"""JWT verification — signature, expiry, issuer, claim presence."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt as pyjwt
import redis.asyncio as redis_async


class TokenInvalid(Exception):
    """JWT failed signature, issuer, or required-claim checks."""


class TokenExpired(Exception):
    """JWT expired."""


class TokenReplayed(Exception):
    """JWT jti already seen (set by JwtReplayGuard in T8)."""


@dataclass(frozen=True)
class JwtClaims:
    iss: str
    sub: str
    obj: str
    case: str
    jti: str
    iat: int
    exp: int


_REQUIRED = ("iss", "sub", "obj", "case", "jti", "iat", "exp")


class JwtVerifier:
    def __init__(
        self,
        *,
        algorithm: str,
        hmac_secret: str | None = None,
        public_key: str | None = None,
        required_iss: str | None = None,
    ) -> None:
        if algorithm == "HS256":
            if not hmac_secret:
                raise ValueError("HS256 requires hmac_secret")
            self._key: str = hmac_secret
        elif algorithm == "RS256":
            if not public_key:
                raise ValueError("RS256 requires public_key")
            self._key = public_key
        else:
            raise ValueError(f"unsupported algorithm: {algorithm}")
        self._alg = algorithm
        self._iss = required_iss

    def verify(self, token: str) -> JwtClaims:
        try:
            payload: dict[str, Any] = pyjwt.decode(
                token,
                self._key,
                algorithms=[self._alg],
                issuer=self._iss,
                options={"require": list(_REQUIRED)},
            )
        except pyjwt.ExpiredSignatureError as e:
            raise TokenExpired(str(e)) from e
        except pyjwt.PyJWTError as e:
            raise TokenInvalid(str(e)) from e

        return JwtClaims(
            iss=payload["iss"],
            sub=payload["sub"],
            obj=payload["obj"],
            case=payload["case"],
            jti=payload["jti"],
            iat=int(payload["iat"]),
            exp=int(payload["exp"]),
        )


class JwtReplayGuard:
    """SETNX-based replay protection. Records jti in Redis with TTL = remaining lifetime."""

    def __init__(self, redis: redis_async.Redis[bytes]) -> None:
        self._redis = redis

    async def claim(self, claims: JwtClaims) -> None:
        remaining = max(1, claims.exp - int(time.time()))
        ok = await self._redis.set(f"jti:{claims.jti}", "1", ex=remaining, nx=True)
        if not ok:
            raise TokenReplayed(claims.jti)
