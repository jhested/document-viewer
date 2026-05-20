"""Optional embeddable HTML+JS shell."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Response

router = APIRouter()
_EMBED_DIR = Path(__file__).resolve().parents[4] / "services" / "embed"


def _read(name: str) -> str:
    return (_EMBED_DIR / name).read_text(encoding="utf-8")


@router.get("/embed/main.js")
async def embed_js() -> Response:
    return Response(content=_read("main.js"), media_type="application/javascript")


@router.get("/embed/{jwt}")
async def embed(jwt: str) -> Response:
    # JSON-encode the token and strip the surrounding quotes so it lands safely
    # inside the `data-token="..."` attribute even with quotes/backslashes.
    safe_token = json.dumps(jwt)[1:-1]
    html = _read("index.html").replace("__JWT__", safe_token)
    return Response(content=html, media_type="text/html")
