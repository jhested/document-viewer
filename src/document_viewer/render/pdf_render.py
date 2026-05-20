"""PDF page rasterization via pypdfium2 (PDFium — Apache-2.0)."""
from __future__ import annotations

import io
from types import TracebackType

import pypdfium2 as pdfium
from PIL import Image

from document_viewer.shared.errors import PageOutOfRange


class PdfDocument:
    def __init__(self, doc: pdfium.PdfDocument) -> None:
        self._doc = doc

    @classmethod
    def from_bytes(cls, data: bytes) -> PdfDocument:
        return cls(pdfium.PdfDocument(io.BytesIO(data)))

    @property
    def page_count(self) -> int:
        return len(self._doc)

    def page_dims(self) -> list[tuple[int, int]]:
        """Width and height of each page in PDF points (1/72")."""
        dims: list[tuple[int, int]] = []
        for i in range(len(self._doc)):
            page = self._doc[i]
            w, h = page.get_size()
            dims.append((int(w), int(h)))
        return dims

    def __enter__(self) -> PdfDocument:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._doc.close()


def render_page(
    doc: PdfDocument,
    *,
    page_index: int,
    width: int,
    max_dpi: int = 300,
) -> Image.Image:
    if page_index < 0 or page_index >= doc.page_count:
        raise PageOutOfRange(page_index)
    page = doc._doc[page_index]
    pt_width, _ = page.get_size()
    target_dpi = min(max_dpi, max(72, round(width / pt_width * 72)))
    scale = target_dpi / 72.0
    bitmap = page.render(scale=scale)
    img: Image.Image = bitmap.to_pil()
    bitmap.close()
    return img.convert("RGB")
