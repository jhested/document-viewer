"""arq job functions executed by the worker."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from document_viewer.render.pipeline import RenderJob
from document_viewer.shared.cache_keys import page_key
from document_viewer.shared.mime import detect_mime


async def _collect(stream: AsyncIterator[bytes]) -> bytes:
    out = b""
    async for chunk in stream:
        out += chunk
    return out


async def _load_source(ctx: dict[str, Any], obj: str) -> tuple[bytes, str, str]:
    chunks, etag = await ctx["source"].fetch(obj)
    body = await _collect(chunks)
    mime = detect_mime(body[:4096], allowed=ctx["settings"].allowed_mimes)
    return body, etag, mime


async def render_manifest(
    ctx: dict[str, Any],
    *,
    obj: str,
    sub: str,
    case: str,
    jti: str,
    watermark_text: str,
) -> dict[str, Any]:
    body, etag, mime = await _load_source(ctx, obj)
    job = RenderJob(source_bytes=body, mime=mime, watermark_text=watermark_text)
    manifest = await ctx["pipeline"].manifest(job)
    payload = {
        "mime": manifest.mime,
        "pages": manifest.pages,
        "dims": [{"w": w, "h": h} for w, h in manifest.dims],
        "etag": etag,
    }
    key = f"manifest:{etag}:{sub}:{jti}"
    await ctx["redis"].set(key, json.dumps(payload), ex=ctx["settings"].cache_ttl_seconds)
    return payload


async def render_page(
    ctx: dict[str, Any],
    *,
    obj: str,
    sub: str,
    case: str,
    jti: str,
    page: int,
    width: int,
    watermark_text: str,
) -> bytes:
    etag = await ctx["source"].head(obj)
    cache_key = page_key(etag=etag, sub=sub, page=page, width=width)
    cached: bytes | None = await ctx["redis"].get(cache_key)
    if cached is not None:
        return bytes(cached)
    body, _, mime = await _load_source(ctx, obj)
    job = RenderJob(source_bytes=body, mime=mime, watermark_text=watermark_text)
    webp: bytes = await ctx["pipeline"].render_page(job, page=page, width=width)
    await ctx["redis"].set(cache_key, webp, ex=ctx["settings"].cache_ttl_seconds)
    return webp
