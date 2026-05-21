# document-viewer

Safe, watermarking document renderer for KYC/AML and other PII-sensitive workflows. Converts PDF, office documents, and images into per-page WebP images via a stateless HTTP API — source bytes never reach the consumer browser.

[![CI](https://github.com/jhested/document-viewer/actions/workflows/ci.yml/badge.svg)](https://github.com/jhested/document-viewer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What it does

- Renders PDF and office documents (docx/xlsx/pptx/odt) into watermarked per-page WebP images server-side.
- Office formats are converted to PDF in an isolated Gotenberg container, then rasterized; original bytes never reach the browser.
- Stateless: callers issue a short-lived JWT scoped to a single object and user; the viewer renders, watermarks, and caches the result for the duration of that token.
- Lazy per-page rendering: large PDFs only render the pages that are viewed.

## What it explicitly does NOT do

- Allow downloading the original file.
- Render documents client-side (no pdf.js, no mammoth).
- Provide editing, annotation, OCR, or text extraction.
- Prevent screenshots / screen recording (no software can).

See `docs/security/known-limitations.md` for the complete honest list.

## Quickstart

```bash
git clone https://github.com/jhested/document-viewer.git
cd document-viewer
cp .env.example .env
docker compose up -d
# open http://localhost:8000/embed/<jwt> to view a document
```

See `docs/getting-started/quickstart.md` for the full 5-minute demo.

## Documentation

- [Quickstart](docs/getting-started/quickstart.md)
- [Architecture overview](docs/architecture/overview.md)
- [API reference](docs/api/reference.md)
- [Helm chart](docs/getting-started/installation-helm.md)
- [Threat model](docs/security/threat-model.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT — see [LICENSE](LICENSE).
