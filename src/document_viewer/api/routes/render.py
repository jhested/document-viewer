"""/render routes: manifest and page."""
from __future__ import annotations

from typing import Annotated, Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Response

from document_viewer.api.deps import (
    get_arq_pool,
    get_jwt_verifier,
    get_rate_limiter,
    get_replay_guard,
    get_settings,
)
from document_viewer.shared.config import Settings
from document_viewer.shared.jwt_auth import (
    JwtClaims,
    JwtReplayGuard,
    JwtVerifier,
    TokenExpired,
    TokenInvalid,
    TokenReplayed,
)
from document_viewer.shared.ratelimit import JtiRateLimiter

router = APIRouter(prefix="/render")

SettingsDep = Annotated[Settings, Depends(get_settings)]
VerifierDep = Annotated[JwtVerifier, Depends(get_jwt_verifier)]
ReplayDep = Annotated[JwtReplayGuard, Depends(get_replay_guard)]
RateLimiterDep = Annotated[JtiRateLimiter, Depends(get_rate_limiter)]
ArqDep = Annotated[ArqRedis, Depends(get_arq_pool)]


async def _verify(jwt: str, verifier: JwtVerifier) -> JwtClaims:
    try:
        return verifier.verify(jwt)
    except TokenExpired as e:
        raise HTTPException(status_code=401, detail="token expired") from e
    except TokenInvalid as e:
        raise HTTPException(status_code=401, detail="token invalid") from e


async def _claims(
    jwt: str, verifier: JwtVerifier, replay: JwtReplayGuard
) -> JwtClaims:
    """Verify and burn the token's jti (manifest path)."""
    claims = await _verify(jwt, verifier)
    try:
        await replay.claim(claims)
    except TokenReplayed as e:
        raise HTTPException(status_code=401, detail="token replayed") from e
    return claims


@router.get("/{jwt}/manifest")
async def manifest(
    jwt: str,
    response: Response,
    settings: SettingsDep,
    verifier: VerifierDep,
    replay: ReplayDep,
    rate_limiter: RateLimiterDep,
    arq: ArqDep,
) -> dict[str, Any]:
    claims = await _claims(jwt, verifier, replay)
    await rate_limiter.check(claims.jti)
    watermark = f"{claims.sub} - {claims.case}"
    job = await arq.enqueue_job(
        "render_manifest",
        obj=claims.obj,
        sub=claims.sub,
        case=claims.case,
        jti=claims.jti,
        watermark_text=watermark,
    )
    if job is None:
        raise HTTPException(status_code=503, detail="job queue unavailable")
    payload = await job.result(timeout=settings.render_timeout_seconds)
    response.headers["Cache-Control"] = "no-store"
    return {**payload, "ttl_seconds": settings.cache_ttl_seconds}


@router.get("/{jwt}/page/{n}")
async def page(
    jwt: str,
    n: int,
    settings: SettingsDep,
    verifier: VerifierDep,
    rate_limiter: RateLimiterDep,
    arq: ArqDep,
    w: int = 1200,
) -> Response:
    # Page renders accept the JWT for its entire validity window so the
    # /embed/{jwt} shell can fetch /manifest + N pages with one token. The
    # one-time replay-claim happens on /manifest (the canonical access gate);
    # individual page fetches only re-verify signature, issuer, and expiry.
    claims = await _verify(jwt, verifier)
    await rate_limiter.check(claims.jti)
    width = min(max(1, w), settings.max_page_width)
    watermark = f"{claims.sub} - {claims.case}"
    job = await arq.enqueue_job(
        "render_page",
        obj=claims.obj,
        sub=claims.sub,
        case=claims.case,
        jti=claims.jti,
        page=n,
        width=width,
        watermark_text=watermark,
    )
    if job is None:
        raise HTTPException(status_code=503, detail="job queue unavailable")
    webp = await job.result(timeout=settings.render_timeout_seconds)
    return Response(
        content=webp,
        media_type="image/webp",
        headers={"Cache-Control": "no-store"},
    )
