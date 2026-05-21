"""Defense-in-depth PDF sanitization before pypdfium2 sees the file."""

from __future__ import annotations

import io

import pikepdf

_DANGEROUS_ROOT_KEYS = (
    "/OpenAction",
    "/AA",
    "/AcroForm",
    "/Names",
    "/JavaScript",
    "/JS",
)


def clean_pdf(data: bytes) -> bytes:
    """Strip JS, embedded files, OpenAction, AA, Launch actions, attachments, encryption."""
    try:
        pdf = pikepdf.open(io.BytesIO(data))
    except pikepdf.PasswordError as e:
        raise RuntimeError("pdf is encrypted; refusing to render") from e

    root = pdf.Root
    # Remove dangerous root-level keys
    for k in _DANGEROUS_ROOT_KEYS:
        if k in root:
            del root[k]

    # Remove per-page additional-actions and annotation JS
    for page in pdf.pages:
        if "/AA" in page:
            del page["/AA"]  # type: ignore[operator]
        if "/Annots" in page:
            for annot in page["/Annots"]:
                for k in ("/A", "/AA", "/JS"):
                    if k in annot:
                        del annot[k]

    # Strip embedded files / attachments
    if "/Names" in root:
        names = root["/Names"]
        for k in ("/EmbeddedFiles", "/JavaScript"):
            if k in names:
                del names[k]

    buf = io.BytesIO()
    pdf.save(buf, linearize=False, qdf=False)
    return buf.getvalue()
