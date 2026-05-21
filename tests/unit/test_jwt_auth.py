"""Unit tests for JWT verification."""

from __future__ import annotations

import time

import fakeredis.aioredis  # type: ignore[import-not-found]
import jwt as pyjwt
import pytest

from document_viewer.shared.jwt_auth import (
    JwtClaims,
    JwtReplayGuard,
    JwtVerifier,
    TokenExpired,
    TokenInvalid,
    TokenReplayed,
)

SECRET = "test-secret-that-is-long-enough-for-hs256"


def _make_token(**overrides: object) -> str:
    payload = {
        "iss": "back-office",
        "sub": "alice@bank.com",
        "obj": "kyc/case-123/passport.pdf",
        "case": "case-123",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
        "jti": "uuid-1",
    }
    payload.update(overrides)  # type: ignore[arg-type]
    return pyjwt.encode(payload, SECRET, algorithm="HS256")


def test_verifies_valid_token() -> None:
    v = JwtVerifier(algorithm="HS256", hmac_secret=SECRET, required_iss="back-office")
    claims = v.verify(_make_token())
    assert isinstance(claims, JwtClaims)
    assert claims.sub == "alice@bank.com"
    assert claims.obj == "kyc/case-123/passport.pdf"
    assert claims.case == "case-123"
    assert claims.jti == "uuid-1"


def test_rejects_expired_token() -> None:
    v = JwtVerifier(algorithm="HS256", hmac_secret=SECRET, required_iss="back-office")
    expired = _make_token(exp=int(time.time()) - 1)
    with pytest.raises(TokenExpired):
        v.verify(expired)


def test_rejects_wrong_signature() -> None:
    v = JwtVerifier(algorithm="HS256", hmac_secret=SECRET, required_iss="back-office")
    with pytest.raises(TokenInvalid):
        bad_token = pyjwt.encode(
            {"sub": "x", "exp": time.time() + 60},
            "different-secret-that-is-long-enough-hs256",
            algorithm="HS256",
        )
        v.verify(bad_token)


def test_rejects_wrong_issuer() -> None:
    v = JwtVerifier(algorithm="HS256", hmac_secret=SECRET, required_iss="back-office")
    with pytest.raises(TokenInvalid):
        v.verify(_make_token(iss="evil-app"))


def test_rejects_missing_required_claim() -> None:
    v = JwtVerifier(algorithm="HS256", hmac_secret=SECRET, required_iss="back-office")
    no_obj = pyjwt.encode(
        {
            "iss": "back-office",
            "sub": "x",
            "exp": int(time.time()) + 60,
            "iat": int(time.time()),
            "jti": "x",
            "case": "x",
        },
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenInvalid):
        v.verify(no_obj)


@pytest.mark.asyncio
async def test_first_use_passes_then_replay_fails() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    guard = JwtReplayGuard(redis)
    claims = JwtClaims(
        iss="i", sub="s", obj="o", case="c", jti="uuid-1", iat=0, exp=int(time.time()) + 60
    )
    await guard.claim(claims)  # ok
    with pytest.raises(TokenReplayed):
        await guard.claim(claims)


@pytest.mark.asyncio
async def test_replay_guard_ttl_matches_token_remaining_lifetime() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    guard = JwtReplayGuard(redis)
    claims = JwtClaims(
        iss="i",
        sub="s",
        obj="o",
        case="c",
        jti="uuid-2",
        iat=int(time.time()),
        exp=int(time.time()) + 30,
    )
    await guard.claim(claims)
    ttl = await redis.ttl(f"jti:{claims.jti}")
    assert 25 <= ttl <= 30
