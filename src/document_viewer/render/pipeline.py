"""Pipeline dispatcher: routes a source to PDF or image rendering, applies watermark."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from document_viewer.render.gotenberg_client import GotenbergClient
from document_viewer.render.image_pipeline import encode_webp, render_image
from document_viewer.render.pdf_clean import clean_pdf
from document_viewer.render.pdf_render import PdfDocument, render_page
from document_viewer.shared.errors import TooManyPages
from document_viewer.shared.watermark import WatermarkConfig, apply_watermark

OFFICE_MIMES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.presentation",
        "application/rtf",
    }
)

IMAGE_MIMES = frozenset(
    {"image/png", "image/jpeg", "image/webp", "image/heic", "image/tiff", "image/gif"}
)


@dataclass(frozen=True)
class RenderJob:
    source_bytes: bytes
    mime: str
    watermark_text: str


@dataclass(frozen=True)
class Manifest:
    mime: str
    pages: int
    dims: list[tuple[int, int]]


class RenderPipeline:
    def __init__(
        self,
        *,
        gotenberg: GotenbergClient,
        settings: object,
        watermark: WatermarkConfig,
    ) -> None:
        self._gotenberg = gotenberg
        self._settings = settings
        self._watermark = watermark

    async def _to_clean_pdf(self, job: RenderJob) -> bytes:
        if job.mime == "application/pdf":
            raw = job.source_bytes
        elif job.mime in OFFICE_MIMES:
            raw = await self._gotenberg.convert_to_pdf(filename="src", data=job.source_bytes)
        else:
            raise ValueError(f"unsupported mime for pdf pipeline: {job.mime}")
        # Reject by page count before the (expensive) sanitization pass.
        max_pages: int = self._settings.max_pages  # type: ignore[attr-defined]
        pages = await asyncio.to_thread(_pdf_page_count, raw)
        if pages > max_pages:
            raise TooManyPages(f"pdf has {pages} pages; max is {max_pages}")
        return await asyncio.to_thread(clean_pdf, raw)

    async def manifest(self, job: RenderJob) -> Manifest:
        if job.mime in IMAGE_MIMES:
            return Manifest(mime=job.mime, pages=1, dims=[(0, 0)])
        pdf = await self._to_clean_pdf(job)
        return await asyncio.to_thread(_pdf_manifest, pdf, job.mime)

    async def render_page(self, job: RenderJob, *, page: int, width: int) -> bytes:
        capped_width = min(width, self._settings.max_page_width)  # type: ignore[attr-defined]
        if job.mime in IMAGE_MIMES:
            return await asyncio.to_thread(
                render_image,
                job.source_bytes,
                mime=job.mime,
                width=capped_width,
                watermark_text=job.watermark_text,
                watermark_config=self._watermark,
            )
        pdf = await self._to_clean_pdf(job)
        return await asyncio.to_thread(
            _render_page_sync,
            pdf,
            page=page,
            width=capped_width,
            watermark_text=job.watermark_text,
            watermark_config=self._watermark,
        )


def _pdf_manifest(pdf: bytes, mime: str) -> Manifest:
    with PdfDocument.from_bytes(pdf) as doc:
        return Manifest(mime=mime, pages=doc.page_count, dims=doc.page_dims())


def _pdf_page_count(pdf: bytes) -> int:
    with PdfDocument.from_bytes(pdf) as doc:
        return doc.page_count


def _render_page_sync(
    pdf: bytes,
    *,
    page: int,
    width: int,
    watermark_text: str,
    watermark_config: WatermarkConfig,
) -> bytes:
    with PdfDocument.from_bytes(pdf) as doc:
        img = render_page(doc, page_index=page - 1, width=width)
    watermarked = apply_watermark(img, text=watermark_text, config=watermark_config)
    return encode_webp(watermarked)
