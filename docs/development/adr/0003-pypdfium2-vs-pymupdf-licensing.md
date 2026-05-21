# pypdfium2 vs PyMuPDF (licensing)

- Status: Accepted
- Date: 2026-05-20

## Context and Problem Statement

We need a Python PDF rendering library to rasterise cleaned PDF pages into RGB bitmaps that Pillow then watermarks and encodes as WebP. The two mature options in the Python ecosystem are [PyMuPDF](https://pymupdf.readthedocs.io/) (which wraps MuPDF) and [pypdfium2](https://pypi.org/project/pypdfium2/) (which wraps Chromium's PDFium). The `document-viewer` project is MIT-licensed and intended to be distributed as a container image that operators run as a network-facing service.

## Decision Drivers

- The project itself is MIT-licensed and we want to keep a permissive licence posture for the published images.
- PyMuPDF is AGPL-3.0; AGPL's network-use clause would obligate any operator running the image on a network service to publish source modifications.
- We want a maintained, well-tested PDF backend.
- The rendering API needs to expose page-level rasterisation at a configurable DPI.

## Considered Options

- `pypdfium2` (Apache-2.0 / BSD-3-Clause; wraps Google's PDFium).
- `PyMuPDF` (AGPL-3.0; wraps MuPDF).
- `pdf2image` + Poppler (CLI-based, slower, less control over render parameters).
- Hand-rolled `ctypes` binding to PDFium.

## Decision Outcome

Chosen option: "pypdfium2", because it provides a permissively-licensed binding to a Google-maintained PDF engine and matches our rendering needs. See `pyproject.toml` — pypdfium2, pikepdf, and Pillow are all permissive.

### Consequences

- Good, because operators can deploy the image without inheriting AGPL obligations.
- Good, because PDFium is maintained by Google and tested at Chromium scale.
- Bad, because pypdfium2 ships a prebuilt native PDFium and we must track its binary release cadence.
- Neutral: API surface differs from PyMuPDF, but the operations we need (open, page count, render to bitmap) are straightforward.
