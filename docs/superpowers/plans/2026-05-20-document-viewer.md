# Document Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Docker-deployed, MIT-licensed render service that safely transforms KYC/AML documents (PDF, office, images) into watermarked per-page WebP images, returned through a stateless HTTP API.

**Architecture:** Three containers — `viewer-api` (FastAPI), `viewer-worker` (render pipelines), and upstream `gotenberg/gotenberg:8` for office→PDF conversion — plus Redis for queue + cache. Source bytes never reach the browser; office rendering is isolated by orchestrator policy. All design decisions captured in `docs/superpowers/specs/2026-05-20-document-viewer-design.md`.

**Tech Stack:** Python 3.12, FastAPI, arq (async Redis queue), pypdfium2 (PDF rasterization, Apache-2.0), pikepdf (PDF sanitization, MPL-2.0), Pillow (image processing), python-magic (mime detection), aioboto3 (S3/MinIO), PyJWT, httpx (Gotenberg client), pytest. Compose v2 + podman-compose for local; Helm chart for k8s.

**Working directory for all paths in this plan:** `document-viewer/` at the repo root.

---

## File Structure

This is the final layout produced by the plan. Each path is owned by one or more specific tasks.

```
document-viewer/
├── LICENSE                              (T1)
├── README.md                            (T2)
├── SECURITY.md                          (T2)
├── CONTRIBUTING.md                      (T2)
├── CODE_OF_CONDUCT.md                   (T2)
├── CHANGELOG.md                         (T2)
├── .gitignore                           (T1)
├── .editorconfig                        (T1)
├── pyproject.toml                       (T3)
├── ruff.toml                            (T3)
├── mypy.ini                             (T3)
├── .env.example                         (T28)
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md                (T4)
│   │   ├── feature_request.md           (T4)
│   │   └── security.md                  (T4)
│   ├── PULL_REQUEST_TEMPLATE.md         (T4)
│   └── workflows/
│       ├── ci.yml                       (T4)
│       ├── codeql.yml                   (T4)
│       ├── release.yml                  (T31)
│       └── sbom.yml                     (T31)
├── src/document_viewer/
│   ├── __init__.py                      (T3)
│   ├── shared/
│   │   ├── __init__.py                  (T3)
│   │   ├── config.py                    (T5)
│   │   ├── logging.py                   (T6)
│   │   ├── jwt_auth.py                  (T7, T8)
│   │   ├── source.py                    (T9, T10)
│   │   ├── mime.py                      (T11)
│   │   ├── cache_keys.py                (T12)
│   │   ├── watermark.py                 (T13)
│   │   └── errors.py                    (T14)
│   ├── render/
│   │   ├── __init__.py                  (T15)
│   │   ├── pdf_clean.py                 (T15)
│   │   ├── pdf_render.py                (T16)
│   │   ├── image_pipeline.py            (T17)
│   │   ├── gotenberg_client.py          (T18)
│   │   └── pipeline.py                  (T19)
│   ├── worker/
│   │   ├── __init__.py                  (T20)
│   │   ├── settings.py                  (T20)
│   │   └── jobs.py                      (T21)
│   └── api/
│       ├── __init__.py                  (T22)
│       ├── app.py                       (T22)
│       ├── deps.py                      (T22)
│       ├── routes/
│       │   ├── __init__.py              (T23)
│       │   ├── health.py                (T23)
│       │   ├── render.py                (T24, T25)
│       │   └── embed.py                 (T26)
│       └── middleware.py                (T27)
├── services/
│   ├── api/Dockerfile                   (T29)
│   ├── worker/Dockerfile                (T29)
│   └── embed/
│       ├── index.html                   (T26)
│       └── main.js                      (T26)
├── compose.yaml                         (T30)
├── compose.test.yaml                    (T30)
├── helm/document-viewer/
│   ├── Chart.yaml                       (T32)
│   ├── values.yaml                      (T32)
│   ├── values.example.yaml              (T32)
│   └── templates/
│       ├── _helpers.tpl                 (T32)
│       ├── api-deployment.yaml          (T33)
│       ├── api-service.yaml             (T33)
│       ├── api-ingress.yaml             (T33)
│       ├── worker-deployment.yaml       (T34)
│       ├── gotenberg-deployment.yaml    (T35)
│       ├── gotenberg-service.yaml       (T35)
│       ├── gotenberg-networkpolicy.yaml (T35)
│       ├── redis.yaml                   (T35)
│       ├── configmap.yaml               (T36)
│       ├── secret.yaml                  (T36)
│       ├── hpa.yaml                     (T36)
│       └── servicemonitor.yaml          (T36)
├── tests/
│   ├── conftest.py                      (T5)
│   ├── unit/
│   │   ├── test_config.py               (T5)
│   │   ├── test_logging.py              (T6)
│   │   ├── test_jwt_auth.py             (T7, T8)
│   │   ├── test_source_fs.py            (T9)
│   │   ├── test_source_s3.py            (T10)
│   │   ├── test_mime.py                 (T11)
│   │   ├── test_cache_keys.py           (T12)
│   │   ├── test_watermark.py            (T13)
│   │   ├── test_errors.py               (T14)
│   │   ├── test_pdf_clean.py            (T15)
│   │   ├── test_pdf_render.py           (T16)
│   │   ├── test_image_pipeline.py       (T17)
│   │   ├── test_gotenberg_client.py     (T18)
│   │   ├── test_pipeline.py             (T19)
│   │   └── test_worker_jobs.py          (T21)
│   ├── integration/
│   │   ├── conftest.py                  (T37)
│   │   ├── test_e2e_pdf.py              (T38)
│   │   ├── test_e2e_docx.py             (T39)
│   │   ├── test_e2e_image.py            (T40)
│   │   ├── test_e2e_cache.py            (T41)
│   │   └── test_e2e_auth.py             (T42)
│   ├── security_corpus/
│   │   ├── README.md                    (T43)
│   │   ├── pdfs/                        (T43)
│   │   ├── docx/                        (T43)
│   │   ├── images/                      (T43)
│   │   └── test_corpus.py               (T43)
│   └── fixtures/                        (T5)
└── docs/
    ├── index.md                         (T44)
    ├── getting-started/
    │   ├── quickstart.md                (T44)
    │   ├── installation-compose.md      (T44)
    │   └── installation-helm.md         (T44)
    ├── architecture/
    │   ├── overview.md                  (T45)
    │   ├── data-flow.md                 (T45)
    │   └── component-reference.md       (T45)
    ├── api/
    │   ├── reference.md                 (T46)
    │   └── jwt.md                       (T46)
    ├── integration/
    │   ├── issuing-tokens.md            (T46)
    │   ├── embedding.md                 (T46)
    │   └── examples/
    │       ├── python.md                (T46)
    │       └── nodejs.md                (T46)
    ├── operations/
    │   ├── configuration.md             (T47)
    │   ├── deployment-compose.md        (T47)
    │   ├── deployment-helm.md           (T47)
    │   ├── monitoring.md                (T47)
    │   ├── tuning.md                    (T47)
    │   └── upgrades.md                  (T47)
    ├── security/
    │   ├── threat-model.md              (T48)
    │   ├── hardening.md                 (T48)
    │   ├── disclosure.md                (T48)
    │   └── known-limitations.md         (T48)
    ├── development/
    │   ├── setup.md                     (T49)
    │   ├── testing.md                   (T49)
    │   ├── release-process.md           (T49)
    │   └── adr/
    │       ├── README.md                (T50)
    │       ├── 0001-render-to-images-not-stream-pdf.md       (T50)
    │       ├── 0002-gotenberg-vs-bespoke-libreoffice.md      (T50)
    │       ├── 0003-pypdfium2-vs-pymupdf-licensing.md        (T50)
    │       └── 0004-jwt-from-upstream-vs-internal-oidc.md    (T50)
    └── design/
        └── 2026-05-20-document-viewer-design.md              (T51)
```

---

## Phase 0 — Project Scaffolding

### Task 1: Repository skeleton, LICENSE, .gitignore, .editorconfig

**Files:**
- Create: `document-viewer/LICENSE`
- Create: `document-viewer/.gitignore`
- Create: `document-viewer/.editorconfig`

- [ ] **Step 1: Create LICENSE (MIT)**

Create `document-viewer/LICENSE`:

```
MIT License

Copyright (c) 2026 Jimmi Hested

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/

# Editors
.vscode/
.idea/
*.swp

# Local env
.env
.env.local

# OS
.DS_Store
Thumbs.db

# Helm
helm/document-viewer/charts/
helm/document-viewer/*.tgz
```

- [ ] **Step 3: Create `.editorconfig`**

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 4
trim_trailing_whitespace = true
insert_final_newline = true

[*.{yaml,yml,json,md,html,js,css}]
indent_size = 2

[Makefile]
indent_style = tab
```

- [ ] **Step 4: Commit**

```bash
cd document-viewer
git add LICENSE .gitignore .editorconfig
git commit -m "chore: add LICENSE (MIT), .gitignore, .editorconfig"
```

---

### Task 2: OSS governance files (README, SECURITY, CONTRIBUTING, CODE_OF_CONDUCT, CHANGELOG)

**Files:**
- Create: `document-viewer/README.md`
- Create: `document-viewer/SECURITY.md`
- Create: `document-viewer/CONTRIBUTING.md`
- Create: `document-viewer/CODE_OF_CONDUCT.md`
- Create: `document-viewer/CHANGELOG.md`

- [ ] **Step 1: Create README.md**

```markdown
# document-viewer

Safe, watermarking document renderer for KYC/AML and other PII-sensitive workflows. Converts PDF, office documents, and images into per-page WebP images via a stateless HTTP API — source bytes never reach the consumer browser.

[![CI](https://github.com/OWNER/document-viewer/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/document-viewer/actions/workflows/ci.yml)
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
git clone https://github.com/OWNER/document-viewer.git
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
```

- [ ] **Step 2: Create SECURITY.md**

```markdown
# Security Policy

## Supported versions

Only the latest minor release receives security fixes.

## Reporting a vulnerability

**Do not open public GitHub issues for security vulnerabilities.**

Email `security@example.com` (replace with maintainer contact before public release) with:

1. A description of the issue and its impact.
2. Reproduction steps or a proof-of-concept.
3. Affected versions if known.

You will receive an acknowledgement within 3 business days.

## Disclosure timeline

- T+0: Report received.
- T+3 days: Acknowledgement sent.
- T+14 days: Initial assessment shared with reporter.
- T+90 days: Coordinated public disclosure, or sooner if a fix is released and verified.

Embargoed CVEs are filed by the maintainers; reporters are credited unless they request anonymity.

## Scope

In scope: the code in this repository, default container images we publish, and the Helm chart.
Out of scope: vulnerabilities in upstream dependencies (Gotenberg, LibreOffice, PDFium, Pillow) — please report those to their respective projects; we will pick up the fix once released.

## Threat model

See `docs/security/threat-model.md` for what this project does and does not defend against.
```

- [ ] **Step 3: Create CONTRIBUTING.md**

```markdown
# Contributing

Thanks for your interest. This project follows TDD — please write the failing test first.

## Local development

Requirements: Python 3.12+, Docker (or Podman) with Compose v2.

```bash
git clone https://github.com/OWNER/document-viewer.git
cd document-viewer
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install   # optional
```

## Running tests

```bash
# Unit tests (fast, no docker)
pytest tests/unit -v

# Integration tests (spins up MinIO + Redis + Gotenberg via compose.test.yaml)
docker compose -f compose.test.yaml up -d
pytest tests/integration -v
docker compose -f compose.test.yaml down

# Security regression corpus
pytest tests/security_corpus -v
```

## Code style

- `ruff` for linting and formatting (config in `ruff.toml`)
- `mypy --strict` for type checking
- Run `ruff check . && ruff format --check . && mypy src/` before opening a PR

## Pull requests

1. Fork and branch from `main`.
2. Write failing tests first; commit them before the implementation.
3. Keep PRs focused — one logical change.
4. Update `CHANGELOG.md` under `## [Unreleased]`.
5. Ensure CI is green.

See `docs/development/setup.md` for the full dev workflow.
```

- [ ] **Step 4: Create CODE_OF_CONDUCT.md**

```markdown
# Code of Conduct

This project adopts the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

By participating, you agree to abide by its terms. Report unacceptable behavior to `conduct@example.com`.
```

- [ ] **Step 5: Create CHANGELOG.md**

```markdown
# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Initial implementation of the document-viewer render service.
```

- [ ] **Step 6: Commit**

```bash
git add README.md SECURITY.md CONTRIBUTING.md CODE_OF_CONDUCT.md CHANGELOG.md
git commit -m "docs: add OSS governance files (README, SECURITY, CONTRIBUTING, COC, CHANGELOG)"
```

---

### Task 3: Python project skeleton (pyproject.toml, ruff, mypy, src layout)

**Files:**
- Create: `document-viewer/pyproject.toml`
- Create: `document-viewer/ruff.toml`
- Create: `document-viewer/mypy.ini`
- Create: `document-viewer/src/document_viewer/__init__.py`
- Create: `document-viewer/src/document_viewer/shared/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "document-viewer"
version = "0.1.0"
description = "Safe, watermarking document renderer for KYC/AML workflows"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.12"
authors = [{ name = "Jimmi Hested" }]
classifiers = [
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Topic :: Security",
    "Topic :: Multimedia :: Graphics :: Viewers",
]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "arq>=0.26",
    "redis>=5.2",
    "httpx>=0.28",
    "aioboto3>=13.2",
    "pyjwt[crypto]>=2.10",
    "pypdfium2>=4.30",
    "pikepdf>=9.4",
    "Pillow>=11.0",
    "pillow-heif>=0.18",
    "python-magic>=0.4.27",
    "structlog>=24.4",
    "pydantic-settings>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "pytest-httpx>=0.34",
    "moto[s3]>=5.0",
    "freezegun>=1.5",
    "ruff>=0.7",
    "mypy>=1.13",
    "types-redis",
    "types-Pillow",
]

[project.scripts]
viewer-api = "document_viewer.api.app:main"
viewer-worker = "document_viewer.worker.settings:main"

[tool.hatch.build.targets.wheel]
packages = ["src/document_viewer"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = ["error"]

[tool.coverage.run]
source = ["src/document_viewer"]
branch = true
```

- [ ] **Step 2: Create ruff.toml**

```toml
line-length = 100
target-version = "py312"

[lint]
select = [
    "E", "F", "W",       # pycodestyle / pyflakes
    "I",                  # isort
    "B",                  # bugbear
    "UP",                 # pyupgrade
    "SIM",                # simplify
    "RUF",                # ruff-specific
    "S",                  # bandit (security)
    "TID",                # tidy imports
    "ASYNC",              # async lints
]
ignore = ["S101"]   # allow `assert` in tests

[lint.per-file-ignores]
"tests/**/*.py" = ["S105", "S106", "S311"]

[format]
quote-style = "double"
```

- [ ] **Step 3: Create mypy.ini**

```ini
[mypy]
python_version = 3.12
strict = true
warn_unused_ignores = true
warn_redundant_casts = true
disallow_untyped_decorators = false
show_error_codes = true
files = src/document_viewer

[mypy-pypdfium2.*]
ignore_missing_imports = true

[mypy-magic]
ignore_missing_imports = true

[mypy-pikepdf.*]
ignore_missing_imports = true
```

- [ ] **Step 4: Create package init files**

`document-viewer/src/document_viewer/__init__.py`:
```python
"""document-viewer — safe document rendering for KYC/AML."""

__version__ = "0.1.0"
```

`document-viewer/src/document_viewer/shared/__init__.py`:
```python
"""Shared modules used by both api and worker."""
```

- [ ] **Step 5: Verify install works**

```bash
cd document-viewer
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -c "import document_viewer; print(document_viewer.__version__)"
```

Expected output: `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml ruff.toml mypy.ini src/
git commit -m "chore: scaffold Python project (pyproject, ruff, mypy, src layout)"
```

---

### Task 4: GitHub templates and CI workflow

**Files:**
- Create: `document-viewer/.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `document-viewer/.github/ISSUE_TEMPLATE/feature_request.md`
- Create: `document-viewer/.github/ISSUE_TEMPLATE/security.md`
- Create: `document-viewer/.github/PULL_REQUEST_TEMPLATE.md`
- Create: `document-viewer/.github/workflows/ci.yml`
- Create: `document-viewer/.github/workflows/codeql.yml`

- [ ] **Step 1: Create issue templates**

`document-viewer/.github/ISSUE_TEMPLATE/bug_report.md`:
```markdown
---
name: Bug report
about: Report something that doesn't work as expected
labels: bug
---

**Describe the bug**

**Reproduction**
1.
2.

**Expected behaviour**

**Actual behaviour**

**Environment**
- Deployment: compose / helm / other
- Version:
- Browser (if relevant):
```

`document-viewer/.github/ISSUE_TEMPLATE/feature_request.md`:
```markdown
---
name: Feature request
about: Suggest an improvement
labels: enhancement
---

**Problem**

**Proposed solution**

**Alternatives considered**
```

`document-viewer/.github/ISSUE_TEMPLATE/security.md`:
```markdown
---
name: Security issue
about: DO NOT use this for vulnerabilities — see SECURITY.md
---

**Stop.** If you've found a vulnerability, email the address in [SECURITY.md](../../SECURITY.md). Public disclosure can harm users until a fix ships.
```

- [ ] **Step 2: Create PR template**

`document-viewer/.github/PULL_REQUEST_TEMPLATE.md`:
```markdown
## Summary

## Test plan
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Security corpus untouched or expanded
- [ ] CHANGELOG.md updated under `[Unreleased]`

## Related
Closes #
```

- [ ] **Step 3: Create CI workflow**

`document-viewer/.github/workflows/ci.yml`:
```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: document-viewer } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy src/

  unit:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: document-viewer } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: sudo apt-get update && sudo apt-get install -y libmagic1
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit -v --cov --cov-report=xml
      - uses: codecov/codecov-action@v5
        with: { files: document-viewer/coverage.xml }

  integration:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: document-viewer } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: sudo apt-get update && sudo apt-get install -y libmagic1
      - run: pip install -e ".[dev]"
      - run: docker compose -f compose.test.yaml up -d --wait
      - run: pytest tests/integration -v
      - if: always()
        run: docker compose -f compose.test.yaml logs > /tmp/compose.log
      - if: always()
        uses: actions/upload-artifact@v4
        with: { name: compose-logs, path: /tmp/compose.log }
      - if: always()
        run: docker compose -f compose.test.yaml down -v

  security-corpus:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: document-viewer } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: sudo apt-get update && sudo apt-get install -y libmagic1
      - run: pip install -e ".[dev]"
      - run: pytest tests/security_corpus -v
```

- [ ] **Step 4: Create CodeQL workflow**

`document-viewer/.github/workflows/codeql.yml`:
```yaml
name: CodeQL

on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
  schedule:
    - cron: "0 6 * * 1"

jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions: { actions: read, contents: read, security-events: write }
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with: { languages: python }
      - uses: github/codeql-action/analyze@v3
```

- [ ] **Step 5: Verify YAML is valid**

```bash
python -c "import yaml; [yaml.safe_load(open(p)) for p in __import__('pathlib').Path('.github').rglob('*.yml')]"
```
Expected: no output (no exceptions).

- [ ] **Step 6: Commit**

```bash
git add .github/
git commit -m "ci: add GitHub templates, CI pipeline, CodeQL scan"
```

---

### Task 5: Test scaffolding (conftest, config module, first passing test)

**Files:**
- Create: `document-viewer/tests/__init__.py`
- Create: `document-viewer/tests/conftest.py`
- Create: `document-viewer/tests/unit/__init__.py`
- Create: `document-viewer/tests/unit/test_config.py`
- Create: `document-viewer/tests/fixtures/.gitkeep`
- Create: `document-viewer/src/document_viewer/shared/config.py`

- [ ] **Step 1: Create empty test packages**

```bash
touch tests/__init__.py tests/unit/__init__.py
mkdir -p tests/fixtures
touch tests/fixtures/.gitkeep
```

- [ ] **Step 2: Write the failing config test**

`document-viewer/tests/unit/test_config.py`:
```python
"""Unit tests for the config module."""
from __future__ import annotations

import pytest

from document_viewer.shared.config import Settings


def test_settings_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SOURCE_BACKEND", "fs")
    monkeypatch.setenv("FS_ROOT", "/tmp/docs")

    s = Settings()

    assert s.jwt_algorithm == "HS256"
    assert s.jwt_hmac_secret.get_secret_value() == "test-secret"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.source_backend == "fs"


def test_settings_defaults() -> None:
    """Defaults are sensible for size caps."""
    s = Settings(
        jwt_algorithm="HS256",
        jwt_hmac_secret="x",
        redis_url="redis://x",
        source_backend="fs",
    )
    assert s.max_source_bytes == 100 * 1024 * 1024
    assert s.max_pages == 500
    assert s.max_page_width == 2400
    assert s.cache_ttl_seconds == 900


def test_settings_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError):
        Settings(
            jwt_algorithm="HS256",
            jwt_hmac_secret="x",
            redis_url="redis://x",
            source_backend="ftp",
        )
```

- [ ] **Step 3: Conftest**

`document-viewer/tests/conftest.py`:
```python
"""Shared pytest fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip viewer-related env vars before each test."""
    for k in list(__import__("os").environ):
        if k.startswith(("JWT_", "S3_", "REDIS_", "MAX_", "CACHE_", "WATERMARK_", "GOTENBERG_", "SOURCE_", "FS_")):
            monkeypatch.delenv(k, raising=False)
```

- [ ] **Step 4: Run test to verify it fails**

```bash
pytest tests/unit/test_config.py -v
```
Expected: `ModuleNotFoundError: No module named 'document_viewer.shared.config'`

- [ ] **Step 5: Implement Settings**

`document-viewer/src/document_viewer/shared/config.py`:
```python
"""Application configuration loaded from environment variables."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Auth
    jwt_algorithm: Literal["HS256", "RS256"] = "RS256"
    jwt_hmac_secret: SecretStr = SecretStr("")
    jwt_public_key: SecretStr = SecretStr("")
    jwt_required_iss: str | None = None

    # Redis
    redis_url: str

    # Source
    source_backend: Literal["s3", "fs"]
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    fs_root: str = "/tmp/docs"

    # Worker
    gotenberg_url: str = "http://gotenberg:3000"
    worker_concurrency: int = 4

    # Limits
    max_source_bytes: int = 100 * 1024 * 1024
    max_pages: int = 500
    max_page_width: int = 2400
    render_timeout_seconds: int = 30
    office_timeout_seconds: int = 60

    # Cache
    cache_ttl_seconds: int = 900

    # Watermark
    watermark_opacity: float = 0.18
    watermark_font_size: int = 24
    watermark_angle: float = -30.0
    watermark_color: str = "#808080"

    # Allowlist
    allowed_mimes: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.oasis.opendocument.text",
            "application/vnd.oasis.opendocument.spreadsheet",
            "application/vnd.oasis.opendocument.presentation",
            "application/rtf",
            "image/png",
            "image/jpeg",
            "image/webp",
            "image/heic",
            "image/tiff",
            "image/gif",
        ]
    )
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/unit/test_config.py -v
```
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add tests/ src/document_viewer/shared/config.py
git commit -m "feat(shared): add Settings config module loaded from env

Pydantic-settings model with JWT, Redis, source backend, size caps,
watermark, and mime allowlist. First TDD cycle of the project."
```

---

## Phase 1 — Shared Modules

### Task 6: Structured logging

**Files:**
- Create: `document-viewer/src/document_viewer/shared/logging.py`
- Create: `document-viewer/tests/unit/test_logging.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_logging.py`:
```python
"""Unit tests for structured logging."""
from __future__ import annotations

import io
import json
import logging

import pytest

from document_viewer.shared.logging import configure_logging, get_logger


def test_logger_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO")
    log = get_logger("test")

    log.info("page_rendered", request_id="abc", sub="alice", page=3, render_ms=145)

    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert payload["event"] == "page_rendered"
    assert payload["request_id"] == "abc"
    assert payload["sub"] == "alice"
    assert payload["page"] == 3
    assert payload["render_ms"] == 145
    assert "timestamp" in payload
    assert payload["level"] == "info"


def test_logger_redacts_jwt_in_message() -> None:
    """A JWT accidentally logged in a message string should be redacted."""
    configure_logging(level="INFO")
    log = get_logger("test")

    redacted = log.redact("path=/render/eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.sig/page/1")
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted
    assert "<jwt>" in redacted
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_logging.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement logging module**

`document-viewer/src/document_viewer/shared/logging.py`:
```python
"""Structured JSON logging on stdout for audit + observability."""
from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            structlog.processors.EventRenamer("event"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        cache_logger_on_first_use=True,
    )


class _Logger:
    def __init__(self, inner: structlog.stdlib.BoundLogger) -> None:
        self._inner = inner

    def info(self, event: str, /, **kwargs: Any) -> None:
        self._inner.info(event, **kwargs)

    def warning(self, event: str, /, **kwargs: Any) -> None:
        self._inner.warning(event, **kwargs)

    def error(self, event: str, /, **kwargs: Any) -> None:
        self._inner.error(event, **kwargs)

    @staticmethod
    def redact(text: str) -> str:
        return _JWT_PATTERN.sub("<jwt>", text)


def get_logger(name: str) -> _Logger:
    return _Logger(structlog.get_logger(name))
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_logging.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/shared/logging.py tests/unit/test_logging.py
git commit -m "feat(shared): structured JSON logging with JWT redaction helper"
```

---

### Task 7: JWT verification (signature + claims)

**Files:**
- Create: `document-viewer/src/document_viewer/shared/jwt_auth.py`
- Create: `document-viewer/tests/unit/test_jwt_auth.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_jwt_auth.py`:
```python
"""Unit tests for JWT verification."""
from __future__ import annotations

import time

import jwt as pyjwt
import pytest

from document_viewer.shared.jwt_auth import (
    JwtClaims,
    JwtVerifier,
    TokenExpired,
    TokenInvalid,
)


SECRET = "test-secret"


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
        v.verify(pyjwt.encode({"sub": "x", "exp": time.time() + 60}, "different-secret", algorithm="HS256"))


def test_rejects_wrong_issuer() -> None:
    v = JwtVerifier(algorithm="HS256", hmac_secret=SECRET, required_iss="back-office")
    with pytest.raises(TokenInvalid):
        v.verify(_make_token(iss="evil-app"))


def test_rejects_missing_required_claim() -> None:
    v = JwtVerifier(algorithm="HS256", hmac_secret=SECRET, required_iss="back-office")
    no_obj = pyjwt.encode(
        {"iss": "back-office", "sub": "x", "exp": int(time.time()) + 60, "iat": int(time.time()), "jti": "x", "case": "x"},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenInvalid):
        v.verify(no_obj)
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_jwt_auth.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement JWT verifier**

`document-viewer/src/document_viewer/shared/jwt_auth.py`:
```python
"""JWT verification — signature, expiry, issuer, claim presence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt as pyjwt


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
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_jwt_auth.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/shared/jwt_auth.py tests/unit/test_jwt_auth.py
git commit -m "feat(shared): JWT verifier with signature, issuer, required-claim checks"
```

---

### Task 8: JWT replay protection via Redis

**Files:**
- Modify: `document-viewer/src/document_viewer/shared/jwt_auth.py`
- Modify: `document-viewer/tests/unit/test_jwt_auth.py`

- [ ] **Step 1: Add failing replay tests**

Append to `document-viewer/tests/unit/test_jwt_auth.py`:
```python
import fakeredis.aioredis  # type: ignore[import-not-found]

from document_viewer.shared.jwt_auth import JwtReplayGuard


@pytest.mark.asyncio
async def test_first_use_passes_then_replay_fails() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    guard = JwtReplayGuard(redis)
    claims = JwtClaims(iss="i", sub="s", obj="o", case="c", jti="uuid-1", iat=0, exp=int(time.time()) + 60)
    await guard.claim(claims)  # ok
    with pytest.raises(TokenReplayed):
        await guard.claim(claims)


@pytest.mark.asyncio
async def test_replay_guard_ttl_matches_token_remaining_lifetime() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    guard = JwtReplayGuard(redis)
    claims = JwtClaims(iss="i", sub="s", obj="o", case="c", jti="uuid-2", iat=int(time.time()), exp=int(time.time()) + 30)
    await guard.claim(claims)
    ttl = await redis.ttl(f"jti:{claims.jti}")
    assert 25 <= ttl <= 30
```

Add `fakeredis>=2.26` to `[project.optional-dependencies].dev` in `pyproject.toml`, then `pip install -e ".[dev]"`.

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_jwt_auth.py -v
```
Expected: `ImportError: cannot import name 'JwtReplayGuard'`.

- [ ] **Step 3: Add JwtReplayGuard to jwt_auth.py**

Append to `document-viewer/src/document_viewer/shared/jwt_auth.py`:
```python
import time

import redis.asyncio as redis_async


class JwtReplayGuard:
    """SETNX-based replay protection. Records jti in Redis with TTL = remaining lifetime."""

    def __init__(self, redis: redis_async.Redis) -> None:
        self._redis = redis

    async def claim(self, claims: JwtClaims) -> None:
        remaining = max(1, claims.exp - int(time.time()))
        ok = await self._redis.set(f"jti:{claims.jti}", "1", ex=remaining, nx=True)
        if not ok:
            raise TokenReplayed(claims.jti)
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_jwt_auth.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_jwt_auth.py src/document_viewer/shared/jwt_auth.py pyproject.toml
git commit -m "feat(shared): JWT replay guard backed by Redis SETNX with TTL"
```

---

### Task 9: Source backend protocol + FilesystemBackend

**Files:**
- Create: `document-viewer/src/document_viewer/shared/source.py`
- Create: `document-viewer/tests/unit/test_source_fs.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_source_fs.py`:
```python
"""Unit tests for the filesystem source backend."""
from __future__ import annotations

from pathlib import Path

import pytest

from document_viewer.shared.source import FilesystemBackend, ObjectNotFound


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "kyc").mkdir()
    (tmp_path / "kyc" / "passport.pdf").write_bytes(b"%PDF-1.7\n...payload...")
    return tmp_path


@pytest.mark.asyncio
async def test_fetch_returns_bytes_and_etag(root: Path) -> None:
    be = FilesystemBackend(root=str(root))
    chunks, etag = await be.fetch("kyc/passport.pdf")
    body = b""
    async for c in chunks:
        body += c
    assert body.startswith(b"%PDF-1.7")
    assert etag.startswith("sha256:")


@pytest.mark.asyncio
async def test_head_returns_etag(root: Path) -> None:
    be = FilesystemBackend(root=str(root))
    etag = await be.head("kyc/passport.pdf")
    assert etag.startswith("sha256:")


@pytest.mark.asyncio
async def test_fetch_raises_for_missing(root: Path) -> None:
    be = FilesystemBackend(root=str(root))
    with pytest.raises(ObjectNotFound):
        await be.fetch("kyc/missing.pdf")


@pytest.mark.asyncio
async def test_rejects_path_traversal(root: Path) -> None:
    be = FilesystemBackend(root=str(root))
    with pytest.raises(ObjectNotFound):
        await be.fetch("../etc/passwd")
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_source_fs.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement source.py**

`document-viewer/src/document_viewer/shared/source.py`:
```python
"""Source backend abstraction. FilesystemBackend for tests; S3Backend (T10) for prod."""
from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol


class ObjectNotFound(Exception):
    """Object key does not exist in the backing store."""


class SourceBackend(Protocol):
    async def fetch(self, key: str) -> tuple[AsyncIterator[bytes], str]: ...
    async def head(self, key: str) -> str: ...


class FilesystemBackend:
    def __init__(self, *, root: str) -> None:
        self._root = Path(root).resolve()

    def _resolve(self, key: str) -> Path:
        target = (self._root / key).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as e:
            raise ObjectNotFound(key) from e
        if not target.is_file():
            raise ObjectNotFound(key)
        return target

    async def head(self, key: str) -> str:
        target = self._resolve(key)
        return _sha256_etag(target)

    async def fetch(self, key: str) -> tuple[AsyncIterator[bytes], str]:
        target = self._resolve(key)
        etag = _sha256_etag(target)

        async def _iter() -> AsyncIterator[bytes]:
            with target.open("rb") as f:
                while chunk := f.read(64 * 1024):
                    yield chunk

        return _iter(), etag


def _sha256_etag(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(64 * 1024):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_source_fs.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/shared/source.py tests/unit/test_source_fs.py
git commit -m "feat(shared): SourceBackend protocol + FilesystemBackend with traversal guard"
```

---

### Task 10: S3Backend (aioboto3) with moto-backed test

**Files:**
- Modify: `document-viewer/src/document_viewer/shared/source.py`
- Create: `document-viewer/tests/unit/test_source_s3.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_source_s3.py`:
```python
"""Unit tests for the S3 source backend, using moto."""
from __future__ import annotations

import pytest
from moto import mock_aws  # type: ignore[import-untyped]

from document_viewer.shared.source import ObjectNotFound, S3Backend


@pytest.mark.asyncio
@mock_aws
async def test_fetch_streams_bytes_and_returns_etag() -> None:
    import boto3

    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="kyc-docs")
    boto3.client("s3", region_name="us-east-1").put_object(
        Bucket="kyc-docs", Key="case-1/passport.pdf", Body=b"%PDF-1.7 hello"
    )

    be = S3Backend(bucket="kyc-docs", region="us-east-1", endpoint_url=None)
    chunks, etag = await be.fetch("case-1/passport.pdf")
    body = b""
    async for c in chunks:
        body += c
    assert body == b"%PDF-1.7 hello"
    assert etag.startswith("s3:")


@pytest.mark.asyncio
@mock_aws
async def test_fetch_missing_raises() -> None:
    import boto3

    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="kyc-docs")
    be = S3Backend(bucket="kyc-docs", region="us-east-1", endpoint_url=None)
    with pytest.raises(ObjectNotFound):
        await be.fetch("missing.pdf")
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_source_s3.py -v
```
Expected: `ImportError: cannot import name 'S3Backend'`.

- [ ] **Step 3: Implement S3Backend**

Append to `document-viewer/src/document_viewer/shared/source.py`:
```python
from collections.abc import AsyncIterator

import aioboto3
from botocore.exceptions import ClientError


class S3Backend:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._session = aioboto3.Session(
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        self._endpoint = endpoint_url

    async def head(self, key: str) -> str:
        async with self._session.client("s3", endpoint_url=self._endpoint) as c:
            try:
                r = await c.head_object(Bucket=self._bucket, Key=key)
            except ClientError as e:
                if e.response["Error"]["Code"] in {"404", "NoSuchKey"}:
                    raise ObjectNotFound(key) from e
                raise
        return f"s3:{r['ETag'].strip('\"')}"

    async def fetch(self, key: str) -> tuple[AsyncIterator[bytes], str]:
        etag = await self.head(key)

        async def _iter() -> AsyncIterator[bytes]:
            async with self._session.client("s3", endpoint_url=self._endpoint) as c:
                r = await c.get_object(Bucket=self._bucket, Key=key)
                async for chunk in r["Body"].iter_chunks(64 * 1024):
                    yield chunk

        return _iter(), etag
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_source_s3.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/shared/source.py tests/unit/test_source_s3.py
git commit -m "feat(shared): S3Backend using aioboto3 with moto-tested 404 handling"
```

---

### Task 11: Mime detection by magic bytes

**Files:**
- Create: `document-viewer/src/document_viewer/shared/mime.py`
- Create: `document-viewer/tests/unit/test_mime.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_mime.py`:
```python
"""Unit tests for magic-byte mime detection."""
from __future__ import annotations

import pytest

from document_viewer.shared.mime import MimeNotAllowed, detect_mime


# Real minimal magic-byte prefixes
PDF_HEADER = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
DOCX_HEADER = b"PK\x03\x04\x14\x00\x06\x00"  # OOXML is a zip
PE_HEADER = b"MZ\x90\x00"


def test_detects_pdf() -> None:
    assert detect_mime(PDF_HEADER, allowed=["application/pdf"]) == "application/pdf"


def test_detects_png() -> None:
    assert detect_mime(PNG_HEADER, allowed=["image/png", "application/pdf"]) == "image/png"


def test_rejects_disallowed_mime() -> None:
    with pytest.raises(MimeNotAllowed) as ei:
        detect_mime(PE_HEADER, allowed=["application/pdf"])
    assert "application/x-dosexec" in str(ei.value) or "application/octet-stream" in str(ei.value)


def test_ignores_extension_in_input() -> None:
    """Function takes bytes only — there's no way to spoof via filename."""
    # PE bytes labelled .pdf is still rejected
    with pytest.raises(MimeNotAllowed):
        detect_mime(PE_HEADER, allowed=["application/pdf"])
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_mime.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement mime.py**

`document-viewer/src/document_viewer/shared/mime.py`:
```python
"""Magic-byte mime detection. Extension is never trusted."""
from __future__ import annotations

import magic


class MimeNotAllowed(Exception):
    """Detected mime is not in the configured allowlist."""

    def __init__(self, detected: str) -> None:
        super().__init__(f"detected mime not allowed: {detected}")
        self.detected = detected


_magic = magic.Magic(mime=True)


def detect_mime(head: bytes, *, allowed: list[str]) -> str:
    """Return the detected mime if it's in allowed; raise MimeNotAllowed otherwise.

    `head` should be the first 4 KB of the source.
    """
    detected = _magic.from_buffer(head)
    if detected not in allowed:
        raise MimeNotAllowed(detected)
    return detected
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_mime.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/shared/mime.py tests/unit/test_mime.py
git commit -m "feat(shared): magic-byte mime detection with allowlist"
```

---

### Task 12: Cache key derivation

**Files:**
- Create: `document-viewer/src/document_viewer/shared/cache_keys.py`
- Create: `document-viewer/tests/unit/test_cache_keys.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_cache_keys.py`:
```python
"""Unit tests for cache key derivation."""
from __future__ import annotations

from document_viewer.shared.cache_keys import cleaned_pdf_key, page_key


def test_page_key_is_deterministic() -> None:
    a = page_key(etag="sha256:abc", sub="alice", page=3, width=1200)
    b = page_key(etag="sha256:abc", sub="alice", page=3, width=1200)
    assert a == b
    assert a.startswith("page:")


def test_page_key_changes_with_any_input() -> None:
    base = page_key(etag="sha256:abc", sub="alice", page=3, width=1200)
    assert base != page_key(etag="sha256:abc", sub="alice", page=3, width=1201)
    assert base != page_key(etag="sha256:abc", sub="alice", page=4, width=1200)
    assert base != page_key(etag="sha256:abc", sub="bob", page=3, width=1200)
    assert base != page_key(etag="sha256:other", sub="alice", page=3, width=1200)


def test_cleaned_pdf_key_uses_jti() -> None:
    a = cleaned_pdf_key(etag="sha256:abc", jti="uuid-1")
    b = cleaned_pdf_key(etag="sha256:abc", jti="uuid-2")
    assert a != b
    assert a.startswith("pdf-clean:")
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_cache_keys.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement cache_keys.py**

`document-viewer/src/document_viewer/shared/cache_keys.py`:
```python
"""Deterministic cache key derivation. Every sensitive input must be in the key."""
from __future__ import annotations

import hashlib


def page_key(*, etag: str, sub: str, page: int, width: int) -> str:
    digest = hashlib.sha256(f"{etag}|{sub}|{page}|{width}".encode()).hexdigest()
    return f"page:{digest}"


def cleaned_pdf_key(*, etag: str, jti: str) -> str:
    digest = hashlib.sha256(f"{etag}|{jti}".encode()).hexdigest()
    return f"pdf-clean:{digest}"
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_cache_keys.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/shared/cache_keys.py tests/unit/test_cache_keys.py
git commit -m "feat(shared): deterministic cache key derivation for pages and cleaned PDFs"
```

---

### Task 13: Watermark rendering

**Files:**
- Create: `document-viewer/src/document_viewer/shared/watermark.py`
- Create: `document-viewer/tests/unit/test_watermark.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_watermark.py`:
```python
"""Unit tests for watermark rendering."""
from __future__ import annotations

from PIL import Image

from document_viewer.shared.watermark import WatermarkConfig, apply_watermark


def test_apply_watermark_returns_image_of_same_size() -> None:
    src = Image.new("RGB", (800, 1000), "white")
    cfg = WatermarkConfig()
    out = apply_watermark(src, text="alice · case-123 · 2026-05-20T14:30Z", config=cfg)
    assert out.size == src.size


def test_apply_watermark_changes_pixels() -> None:
    """The watermark must visibly modify the source pixels."""
    src = Image.new("RGB", (800, 1000), "white")
    out = apply_watermark(src, text="alice", config=WatermarkConfig())
    # Compare a sample band that should overlap a tiled watermark instance
    src_pixels = src.crop((100, 400, 700, 600)).tobytes()
    out_pixels = out.crop((100, 400, 700, 600)).tobytes()
    assert src_pixels != out_pixels


def test_apply_watermark_tiles_so_cropping_leaves_instances() -> None:
    """At least 3 visually distinct watermark bands should be present in a tall image."""
    src = Image.new("RGB", (800, 1600), "white")
    out = apply_watermark(src, text="alice", config=WatermarkConfig())
    bands = [
        out.crop((0, 0, 800, 400)).tobytes(),
        out.crop((0, 400, 800, 800)).tobytes(),
        out.crop((0, 800, 800, 1200)).tobytes(),
        out.crop((0, 1200, 800, 1600)).tobytes(),
    ]
    untouched = Image.new("RGB", (800, 400), "white").tobytes()
    changed = [b for b in bands if b != untouched]
    assert len(changed) >= 3
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_watermark.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement watermark.py**

`document-viewer/src/document_viewer/shared/watermark.py`:
```python
"""Server-side watermark rendering, baked into image pixels."""
from __future__ import annotations

import math
from dataclasses import dataclass
from importlib import resources

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class WatermarkConfig:
    opacity: float = 0.18
    font_size: int = 24
    angle: float = -30.0
    color: tuple[int, int, int] = (128, 128, 128)
    tile_h: int = 350  # vertical spacing between tiled watermarks


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default(size=size)


def apply_watermark(src: Image.Image, *, text: str, config: WatermarkConfig) -> Image.Image:
    base = src.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))

    # Build a single rotated text tile
    font = _load_font(config.font_size)
    bbox = font.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 16
    tile = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    alpha = max(1, min(255, int(255 * config.opacity)))
    ImageDraw.Draw(tile).text((pad, pad), text, fill=(*config.color, alpha), font=font)
    rotated = tile.rotate(config.angle, resample=Image.BICUBIC, expand=True)

    # Tile over the image
    rw, rh = rotated.size
    y = -rh // 2
    row = 0
    while y < base.size[1]:
        x_offset = (rw // 2) if row % 2 else 0
        x = -rw // 2 + x_offset
        while x < base.size[0]:
            overlay.alpha_composite(rotated, (x, y))
            x += rw
        y += int(config.tile_h * math.cos(math.radians(config.angle)))
        row += 1

    return Image.alpha_composite(base, overlay).convert("RGB")
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_watermark.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/shared/watermark.py tests/unit/test_watermark.py
git commit -m "feat(shared): tiled rotated watermark baked into image pixels"
```

---

### Task 14: Error taxonomy

**Files:**
- Create: `document-viewer/src/document_viewer/shared/errors.py`
- Create: `document-viewer/tests/unit/test_errors.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_errors.py`:
```python
"""Unit tests for the error taxonomy."""
from __future__ import annotations

from document_viewer.shared.errors import (
    ObjectTooLarge,
    PageOutOfRange,
    RenderError,
    RenderTimeout,
    UnsupportedMime,
    error_to_http_status,
)


def test_status_mapping() -> None:
    assert error_to_http_status(ObjectTooLarge("100mb")) == 413
    assert error_to_http_status(PageOutOfRange(5)) == 404
    assert error_to_http_status(UnsupportedMime("application/x-msi")) == 415
    assert error_to_http_status(RenderTimeout("page 3")) == 504
    assert error_to_http_status(RenderError("worker crashed")) == 500


def test_render_error_carries_safe_message() -> None:
    e = RenderError("worker crashed")
    assert "worker crashed" in e.safe_message
    # Never echoes source bytes
    assert "%PDF" not in e.safe_message
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_errors.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement errors.py**

`document-viewer/src/document_viewer/shared/errors.py`:
```python
"""Domain error taxonomy. Each maps to a stable HTTP status."""
from __future__ import annotations


class RenderError(Exception):
    """Generic render failure. Carries only operator-safe info, never source bytes."""

    @property
    def safe_message(self) -> str:
        return str(self)


class RenderTimeout(RenderError):
    pass


class ObjectTooLarge(RenderError):
    pass


class PageOutOfRange(RenderError):
    pass


class UnsupportedMime(RenderError):
    pass


def error_to_http_status(e: RenderError) -> int:
    if isinstance(e, ObjectTooLarge):
        return 413
    if isinstance(e, PageOutOfRange):
        return 404
    if isinstance(e, UnsupportedMime):
        return 415
    if isinstance(e, RenderTimeout):
        return 504
    return 500
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_errors.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/shared/errors.py tests/unit/test_errors.py
git commit -m "feat(shared): render error taxonomy with HTTP status mapping"
```

---

## Phase 2 — Render Pipelines

### Task 15: pikepdf cleaner

**Files:**
- Create: `document-viewer/src/document_viewer/render/__init__.py`
- Create: `document-viewer/src/document_viewer/render/pdf_clean.py`
- Create: `document-viewer/tests/unit/test_pdf_clean.py`
- Create: `document-viewer/tests/fixtures/pdf_with_js.pdf` (script in step 1)

- [ ] **Step 1: Generate a fixture PDF containing /JavaScript**

Create `document-viewer/tests/fixtures/_make_pdf_with_js.py` (run once, output committed):
```python
"""One-off fixture builder. Run with `python tests/fixtures/_make_pdf_with_js.py`."""
from pathlib import Path

import pikepdf

p = pikepdf.Pdf.new()
p.add_blank_page(page_size=(595, 842))
p.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS="app.alert('x')")
p.Root.Names = pikepdf.Dictionary(
    JavaScript=pikepdf.Dictionary(
        Names=pikepdf.Array([pikepdf.String("evil"), pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS="bad()")])
    )
)
out = Path(__file__).parent / "pdf_with_js.pdf"
p.save(out)
print(f"wrote {out}")
```

Run it:
```bash
python tests/fixtures/_make_pdf_with_js.py
```

- [ ] **Step 2: Write the failing test**

`document-viewer/tests/unit/test_pdf_clean.py`:
```python
"""Unit tests for the pikepdf pre-rasterization cleaner."""
from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest

from document_viewer.render.pdf_clean import clean_pdf

FIXTURE = Path(__file__).parent.parent / "fixtures" / "pdf_with_js.pdf"


def test_clean_strips_javascript() -> None:
    import io

    raw = FIXTURE.read_bytes()
    cleaned = clean_pdf(raw)
    p = pikepdf.open(io.BytesIO(cleaned))
    root = p.Root
    assert "/OpenAction" not in root.keys()
    if "/Names" in root.keys():
        assert "/JavaScript" not in root.Names.keys()


def test_clean_returns_smaller_or_equal_bytes() -> None:
    raw = FIXTURE.read_bytes()
    cleaned = clean_pdf(raw)
    assert len(cleaned) <= len(raw) + 1024  # allow for restructuring overhead


def test_clean_rejects_encrypted_pdf(tmp_path: Path) -> None:
    encrypted = tmp_path / "enc.pdf"
    p = pikepdf.Pdf.new()
    p.add_blank_page(page_size=(595, 842))
    p.save(encrypted, encryption=pikepdf.Encryption(owner="o", user="u", R=4))
    with pytest.raises(RuntimeError, match="encrypted"):
        clean_pdf(encrypted.read_bytes())
```

- [ ] **Step 3: Run to verify fail**

```bash
pytest tests/unit/test_pdf_clean.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement pdf_clean.py**

`document-viewer/src/document_viewer/render/__init__.py`:
```python
"""Render pipelines: pdf_clean, pdf_render, image_pipeline, gotenberg_client, pipeline."""
```

`document-viewer/src/document_viewer/render/pdf_clean.py`:
```python
"""Defense-in-depth PDF sanitization before pypdfium2 sees the file."""
from __future__ import annotations

import io

import pikepdf

_DANGEROUS_ROOT_KEYS = (
    "/OpenAction", "/AA", "/AcroForm", "/Names", "/JavaScript", "/JS",
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
        if k in root.keys():
            del root[k]

    # Remove per-page additional-actions and annotation JS
    for page in pdf.pages:
        if "/AA" in page.keys():
            del page["/AA"]
        if "/Annots" in page.keys():
            for annot in page["/Annots"]:
                for k in ("/A", "/AA", "/JS"):
                    if k in annot.keys():
                        del annot[k]

    # Strip embedded files / attachments
    if "/Names" in root.keys():
        names = root["/Names"]
        for k in ("/EmbeddedFiles", "/JavaScript"):
            if k in names.keys():
                del names[k]

    buf = io.BytesIO()
    pdf.save(buf, linearize=False, qdf=False)
    return buf.getvalue()
```

- [ ] **Step 5: Run to verify pass**

```bash
pytest tests/unit/test_pdf_clean.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/document_viewer/render/__init__.py src/document_viewer/render/pdf_clean.py \
        tests/unit/test_pdf_clean.py tests/fixtures/_make_pdf_with_js.py tests/fixtures/pdf_with_js.pdf
git commit -m "feat(render): pikepdf cleaner strips JS, OpenAction, AA, attachments, encryption"
```

---

### Task 16: PDF page renderer (pypdfium2)

**Files:**
- Create: `document-viewer/src/document_viewer/render/pdf_render.py`
- Create: `document-viewer/tests/unit/test_pdf_render.py`
- Create: `document-viewer/tests/fixtures/simple.pdf` (script in step 1)

- [ ] **Step 1: Generate a simple multi-page fixture**

`document-viewer/tests/fixtures/_make_simple_pdf.py`:
```python
"""Generate a 3-page PDF with visible text for renderer tests."""
from pathlib import Path

import pikepdf
from pikepdf.canvas import Canvas, Text

c = Canvas(page_size=pikepdf.canvas.LETTER)
for n in (1, 2, 3):
    c.add_text(Text(text=f"page {n}", font_size=48), x=72, y=720)
    c.add_page()
c.save(Path(__file__).parent / "simple.pdf")
```

Run:
```bash
python tests/fixtures/_make_simple_pdf.py
```

- [ ] **Step 2: Write the failing test**

`document-viewer/tests/unit/test_pdf_render.py`:
```python
"""Unit tests for pypdfium2 PDF rendering."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from document_viewer.render.pdf_render import PdfDocument, render_page
from document_viewer.shared.errors import PageOutOfRange

FIXTURE = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


def test_open_returns_page_count_and_dims() -> None:
    with PdfDocument.from_bytes(FIXTURE.read_bytes()) as doc:
        assert doc.page_count == 3
        dims = doc.page_dims()
        assert len(dims) == 3
        for w, h in dims:
            assert w > 0 and h > 0


def test_render_page_produces_image_at_requested_width() -> None:
    with PdfDocument.from_bytes(FIXTURE.read_bytes()) as doc:
        img = render_page(doc, page_index=0, width=1200)
        assert isinstance(img, Image.Image)
        assert 1198 <= img.size[0] <= 1202  # ±1px tolerance


def test_render_page_out_of_range_raises() -> None:
    with PdfDocument.from_bytes(FIXTURE.read_bytes()) as doc:
        with pytest.raises(PageOutOfRange):
            render_page(doc, page_index=99, width=1200)


def test_dpi_is_capped_for_huge_requested_widths() -> None:
    with PdfDocument.from_bytes(FIXTURE.read_bytes()) as doc:
        img = render_page(doc, page_index=0, width=20000, max_dpi=300)
        # 8.5in × 300dpi = 2550 px
        assert img.size[0] <= 2600
```

- [ ] **Step 3: Run to verify fail**

```bash
pytest tests/unit/test_pdf_render.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement pdf_render.py**

`document-viewer/src/document_viewer/render/pdf_render.py`:
```python
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
    def from_bytes(cls, data: bytes) -> "PdfDocument":
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

    def __enter__(self) -> "PdfDocument":
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
    page = doc._doc[page_index]  # noqa: SLF001 — intentional within module
    pt_width, _ = page.get_size()
    target_dpi = min(max_dpi, max(72, round(width / pt_width * 72)))
    scale = target_dpi / 72.0
    bitmap = page.render(scale=scale)
    img = bitmap.to_pil()
    bitmap.close()
    return img.convert("RGB")
```

- [ ] **Step 5: Run to verify pass**

```bash
pytest tests/unit/test_pdf_render.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/document_viewer/render/pdf_render.py tests/unit/test_pdf_render.py \
        tests/fixtures/_make_simple_pdf.py tests/fixtures/simple.pdf
git commit -m "feat(render): pypdfium2 PDF rasterizer with DPI cap"
```

---

### Task 17: Image pipeline (re-encode + watermark + WebP)

**Files:**
- Create: `document-viewer/src/document_viewer/render/image_pipeline.py`
- Create: `document-viewer/tests/unit/test_image_pipeline.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_image_pipeline.py`:
```python
"""Unit tests for the image pipeline (re-encode, EXIF strip, WebP encode)."""
from __future__ import annotations

import io

from PIL import Image
from PIL.ExifTags import TAGS

from document_viewer.render.image_pipeline import encode_webp, render_image
from document_viewer.shared.watermark import WatermarkConfig


def _pil_jpeg_with_exif() -> bytes:
    img = Image.new("RGB", (400, 300), "red")
    exif = img.getexif()
    exif[0x010F] = "ACME Camera"  # Make
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_render_image_strips_exif() -> None:
    raw = _pil_jpeg_with_exif()
    out = render_image(raw, mime="image/jpeg", width=300, watermark_text="t", watermark_config=WatermarkConfig())
    decoded = Image.open(io.BytesIO(out))
    decoded.load()
    assert not decoded.getexif() or 0x010F not in decoded.getexif()


def test_render_image_resizes_to_requested_width() -> None:
    img = Image.new("RGB", (4000, 3000), "blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    out = render_image(buf.getvalue(), mime="image/png", width=800, watermark_text="t", watermark_config=WatermarkConfig())
    decoded = Image.open(io.BytesIO(out))
    assert decoded.size[0] == 800


def test_encode_webp_round_trip() -> None:
    img = Image.new("RGB", (100, 100), "green")
    raw = encode_webp(img)
    decoded = Image.open(io.BytesIO(raw))
    assert decoded.format == "WEBP"
    assert decoded.size == (100, 100)
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_image_pipeline.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement image_pipeline.py**

`document-viewer/src/document_viewer/render/image_pipeline.py`:
```python
"""Image source pipeline: open → strip metadata → resize → watermark → WebP."""
from __future__ import annotations

import io

from PIL import Image

from document_viewer.shared.watermark import WatermarkConfig, apply_watermark

# Re-register HEIC support if pillow-heif is installed
try:
    import pillow_heif  # type: ignore[import-not-found]

    pillow_heif.register_heif_opener()
except ImportError:
    pass

Image.MAX_IMAGE_PIXELS = 200_000_000  # ~200 MP guard against decompression bombs


def encode_webp(img: Image.Image, *, quality: int = 82, method: int = 4) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=method)
    return buf.getvalue()


def render_image(
    data: bytes,
    *,
    mime: str,
    width: int,
    watermark_text: str,
    watermark_config: WatermarkConfig,
) -> bytes:
    src = Image.open(io.BytesIO(data))
    src.load()
    # Drop EXIF / metadata by recreating the image
    cleaned = Image.new(src.mode, src.size)
    cleaned.paste(src)
    # Resize maintaining aspect
    if cleaned.size[0] != width:
        h = round(cleaned.size[1] * (width / cleaned.size[0]))
        cleaned = cleaned.resize((width, h), Image.LANCZOS)
    if cleaned.mode != "RGB":
        cleaned = cleaned.convert("RGB")
    watermarked = apply_watermark(cleaned, text=watermark_text, config=watermark_config)
    return encode_webp(watermarked)
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_image_pipeline.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/render/image_pipeline.py tests/unit/test_image_pipeline.py
git commit -m "feat(render): image pipeline (strip EXIF, resize, watermark, WebP encode)"
```

---

### Task 18: Gotenberg HTTP client

**Files:**
- Create: `document-viewer/src/document_viewer/render/gotenberg_client.py`
- Create: `document-viewer/tests/unit/test_gotenberg_client.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_gotenberg_client.py`:
```python
"""Unit tests for the Gotenberg HTTP client."""
from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from document_viewer.render.gotenberg_client import GotenbergClient, GotenbergError


@pytest.mark.asyncio
async def test_convert_returns_pdf_bytes(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://gotenberg:3000/forms/libreoffice/convert",
        content=b"%PDF-1.7 produced",
        headers={"Content-Type": "application/pdf"},
    )
    client = GotenbergClient(base_url="http://gotenberg:3000", timeout_seconds=60)
    pdf = await client.convert_to_pdf(filename="x.docx", data=b"docx-bytes")
    assert pdf == b"%PDF-1.7 produced"


@pytest.mark.asyncio
async def test_convert_raises_on_500(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://gotenberg:3000/forms/libreoffice/convert",
        status_code=500,
    )
    client = GotenbergClient(base_url="http://gotenberg:3000", timeout_seconds=60)
    with pytest.raises(GotenbergError):
        await client.convert_to_pdf(filename="x.docx", data=b"x")
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_gotenberg_client.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement gotenberg_client.py**

`document-viewer/src/document_viewer/render/gotenberg_client.py`:
```python
"""Async HTTP client for Gotenberg office→PDF conversion."""
from __future__ import annotations

import httpx


class GotenbergError(RuntimeError):
    pass


class GotenbergClient:
    def __init__(self, *, base_url: str, timeout_seconds: int) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def convert_to_pdf(self, *, filename: str, data: bytes) -> bytes:
        files = {"files": (filename, data, "application/octet-stream")}
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(f"{self._base}/forms/libreoffice/convert", files=files)
        if r.status_code != 200:
            raise GotenbergError(f"gotenberg returned {r.status_code}")
        return r.content
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_gotenberg_client.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/render/gotenberg_client.py tests/unit/test_gotenberg_client.py
git commit -m "feat(render): async Gotenberg HTTP client for office→PDF conversion"
```

---

### Task 19: Pipeline dispatcher

**Files:**
- Create: `document-viewer/src/document_viewer/render/pipeline.py`
- Create: `document-viewer/tests/unit/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_pipeline.py`:
```python
"""Unit tests for the pipeline dispatcher."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from document_viewer.render.pipeline import RenderJob, RenderPipeline
from document_viewer.shared.watermark import WatermarkConfig

FIXTURE_PDF = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


@dataclass
class _DummySettings:
    max_page_width: int = 2400
    watermark_opacity: float = 0.18
    watermark_font_size: int = 24
    watermark_angle: float = -30.0
    watermark_color: str = "#808080"
    office_timeout_seconds: int = 60


@pytest.fixture()
def watermark_cfg() -> WatermarkConfig:
    return WatermarkConfig()


@pytest.mark.asyncio
async def test_pdf_pipeline_returns_manifest_and_page(watermark_cfg: WatermarkConfig) -> None:
    pdf_bytes = FIXTURE_PDF.read_bytes()
    pipeline = RenderPipeline(gotenberg=MagicMock(), settings=_DummySettings(), watermark=watermark_cfg)

    job = RenderJob(
        source_bytes=pdf_bytes,
        mime="application/pdf",
        watermark_text="alice",
    )
    manifest = await pipeline.manifest(job)
    assert manifest.pages == 3
    assert len(manifest.dims) == 3

    page = await pipeline.render_page(job, page=1, width=800)
    assert page.startswith(b"RIFF") and b"WEBP" in page[:16]


@pytest.mark.asyncio
async def test_docx_pipeline_calls_gotenberg(watermark_cfg: WatermarkConfig) -> None:
    pdf_bytes = FIXTURE_PDF.read_bytes()
    gotenberg = MagicMock()
    gotenberg.convert_to_pdf = AsyncMock(return_value=pdf_bytes)

    pipeline = RenderPipeline(gotenberg=gotenberg, settings=_DummySettings(), watermark=watermark_cfg)
    job = RenderJob(
        source_bytes=b"docx-bytes",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        watermark_text="alice",
    )
    manifest = await pipeline.manifest(job)
    assert manifest.pages == 3
    gotenberg.convert_to_pdf.assert_awaited_once()
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_pipeline.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement pipeline.py**

`document-viewer/src/document_viewer/render/pipeline.py`:
```python
"""Pipeline dispatcher: routes a source to PDF or image rendering, applies watermark."""
from __future__ import annotations

from dataclasses import dataclass

from document_viewer.render.gotenberg_client import GotenbergClient
from document_viewer.render.image_pipeline import encode_webp, render_image
from document_viewer.render.pdf_clean import clean_pdf
from document_viewer.render.pdf_render import PdfDocument, render_page
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
            return clean_pdf(job.source_bytes)
        if job.mime in OFFICE_MIMES:
            pdf = await self._gotenberg.convert_to_pdf(filename="src", data=job.source_bytes)
            return clean_pdf(pdf)
        raise ValueError(f"unsupported mime for pdf pipeline: {job.mime}")

    async def manifest(self, job: RenderJob) -> Manifest:
        if job.mime in IMAGE_MIMES:
            return Manifest(mime=job.mime, pages=1, dims=[(0, 0)])
        pdf = await self._to_clean_pdf(job)
        with PdfDocument.from_bytes(pdf) as doc:
            return Manifest(mime=job.mime, pages=doc.page_count, dims=doc.page_dims())

    async def render_page(self, job: RenderJob, *, page: int, width: int) -> bytes:
        capped_width = min(width, self._settings.max_page_width)  # type: ignore[attr-defined]
        if job.mime in IMAGE_MIMES:
            return render_image(
                job.source_bytes,
                mime=job.mime,
                width=capped_width,
                watermark_text=job.watermark_text,
                watermark_config=self._watermark,
            )
        pdf = await self._to_clean_pdf(job)
        with PdfDocument.from_bytes(pdf) as doc:
            img = render_page(doc, page_index=page - 1, width=capped_width)
        watermarked = apply_watermark(img, text=job.watermark_text, config=self._watermark)
        return encode_webp(watermarked)
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_pipeline.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/render/pipeline.py tests/unit/test_pipeline.py
git commit -m "feat(render): pipeline dispatcher routes by mime, applies watermark, returns WebP"
```

---

## Phase 3 — Worker

### Task 20: arq worker settings

**Files:**
- Create: `document-viewer/src/document_viewer/worker/__init__.py`
- Create: `document-viewer/src/document_viewer/worker/settings.py`

- [ ] **Step 1: Create worker package**

`document-viewer/src/document_viewer/worker/__init__.py`:
```python
"""arq-based worker that runs the render pipeline."""
```

- [ ] **Step 2: Create worker settings**

`document-viewer/src/document_viewer/worker/settings.py`:
```python
"""arq WorkerSettings + the `viewer-worker` entrypoint."""
from __future__ import annotations

from arq.connections import RedisSettings

from document_viewer.shared.config import Settings
from document_viewer.shared.logging import configure_logging


def _redis_settings(s: Settings) -> RedisSettings:
    return RedisSettings.from_dsn(s.redis_url)


def _functions() -> list[object]:
    # Late import so this module loads even before T21 lands.
    from document_viewer.worker.jobs import render_manifest, render_page
    return [render_manifest, render_page]


class WorkerSettings:
    """Module-level config picked up by `arq document_viewer.worker.settings.WorkerSettings`."""

    functions = _functions()

    @staticmethod
    def on_startup(ctx: dict[str, object]) -> None:
        configure_logging(level="INFO")


def main() -> None:
    """Console-script entry: `viewer-worker`."""
    s = Settings()
    WorkerSettings.redis_settings = _redis_settings(s)
    WorkerSettings.max_jobs = s.worker_concurrency
    import asyncio
    from arq.worker import run_worker

    asyncio.run(run_worker(WorkerSettings))
```

> **Note:** the `functions` list is built lazily by `_functions()`, so this file is importable on its own even before T21 adds `jobs.py`. mypy passes both before and after T21 because the late import is only evaluated when `WorkerSettings.functions` is first accessed at runtime.

- [ ] **Step 3: Commit skeleton (jobs land in T21)**

```bash
git add src/document_viewer/worker/__init__.py src/document_viewer/worker/settings.py
git commit -m "feat(worker): arq WorkerSettings skeleton + viewer-worker entrypoint"
```

---

### Task 21: Worker jobs (render_manifest, render_page) + cache wiring

**Files:**
- Create: `document-viewer/src/document_viewer/worker/jobs.py`
- Create: `document-viewer/tests/unit/test_worker_jobs.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_worker_jobs.py`:
```python
"""Unit tests for the worker job functions."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest

from document_viewer.worker.jobs import render_manifest, render_page

FIXTURE_PDF = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


@pytest.mark.asyncio
async def test_render_manifest_returns_payload() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    pdf = FIXTURE_PDF.read_bytes()

    pipeline = MagicMock()
    pipeline.manifest = AsyncMock(return_value=MagicMock(mime="application/pdf", pages=3, dims=[(595, 842)] * 3))

    source = MagicMock()
    async def _fetch(key: str):
        async def _it():
            yield pdf
        return _it(), "sha256:abc"
    source.fetch = AsyncMock(side_effect=_fetch)
    source.head = AsyncMock(return_value="sha256:abc")

    ctx = {"redis": redis, "pipeline": pipeline, "source": source, "settings": MagicMock(cache_ttl_seconds=900, allowed_mimes=["application/pdf"])}
    out = await render_manifest(ctx, obj="kyc/x.pdf", sub="alice", case="c1", jti="j1", watermark_text="t")
    assert out["pages"] == 3
    assert out["mime"] == "application/pdf"


@pytest.mark.asyncio
async def test_render_page_caches_after_first_render() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    pdf = FIXTURE_PDF.read_bytes()

    pipeline = MagicMock()
    pipeline.render_page = AsyncMock(return_value=b"RIFF\x00\x00\x00\x00WEBPVP8 ")

    source = MagicMock()
    async def _fetch(key: str):
        async def _it():
            yield pdf
        return _it(), "sha256:abc"
    source.fetch = AsyncMock(side_effect=_fetch)
    source.head = AsyncMock(return_value="sha256:abc")

    ctx = {"redis": redis, "pipeline": pipeline, "source": source, "settings": MagicMock(cache_ttl_seconds=900, allowed_mimes=["application/pdf"])}
    out1 = await render_page(ctx, obj="kyc/x.pdf", sub="alice", case="c1", jti="j1", page=1, width=800, watermark_text="t")
    assert out1.startswith(b"RIFF")
    pipeline.render_page.reset_mock()
    out2 = await render_page(ctx, obj="kyc/x.pdf", sub="alice", case="c1", jti="j1", page=1, width=800, watermark_text="t")
    pipeline.render_page.assert_not_awaited()
    assert out2 == out1
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_worker_jobs.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement jobs.py**

`document-viewer/src/document_viewer/worker/jobs.py`:
```python
"""arq job functions executed by the worker."""
from __future__ import annotations

import json
from typing import Any

from document_viewer.render.pipeline import RenderJob
from document_viewer.shared.cache_keys import page_key
from document_viewer.shared.mime import detect_mime


async def _collect(stream: object) -> bytes:
    out = b""
    async for chunk in stream:  # type: ignore[union-attr]
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
    cached = await ctx["redis"].get(cache_key)
    if cached is not None:
        return bytes(cached)
    body, _, mime = await _load_source(ctx, obj)
    job = RenderJob(source_bytes=body, mime=mime, watermark_text=watermark_text)
    webp = await ctx["pipeline"].render_page(job, page=page, width=width)
    await ctx["redis"].set(cache_key, webp, ex=ctx["settings"].cache_ttl_seconds)
    return webp
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_worker_jobs.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/worker/jobs.py tests/unit/test_worker_jobs.py
git commit -m "feat(worker): render_manifest and render_page jobs with Redis cache"
```

---

## Phase 4 — API

### Task 22: FastAPI app skeleton + dependencies

**Files:**
- Create: `document-viewer/src/document_viewer/api/__init__.py`
- Create: `document-viewer/src/document_viewer/api/app.py`
- Create: `document-viewer/src/document_viewer/api/deps.py`

- [ ] **Step 1: Create api package init**

`document-viewer/src/document_viewer/api/__init__.py`:
```python
"""FastAPI app for viewer-api."""
```

- [ ] **Step 2: Implement dependencies**

`document-viewer/src/document_viewer/api/deps.py`:
```python
"""FastAPI dependency providers — Settings, Redis pool, JWT verifier, arq pool."""
from __future__ import annotations

from functools import lru_cache

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
import redis.asyncio as redis_async

from document_viewer.shared.config import Settings
from document_viewer.shared.jwt_auth import JwtReplayGuard, JwtVerifier


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_jwt_verifier() -> JwtVerifier:
    s = get_settings()
    return JwtVerifier(
        algorithm=s.jwt_algorithm,
        hmac_secret=s.jwt_hmac_secret.get_secret_value() or None,
        public_key=s.jwt_public_key.get_secret_value() or None,
        required_iss=s.jwt_required_iss,
    )


async def get_redis() -> redis_async.Redis:
    s = get_settings()
    return redis_async.from_url(s.redis_url, decode_responses=False)


async def get_arq_pool() -> ArqRedis:
    s = get_settings()
    return await create_pool(RedisSettings.from_dsn(s.redis_url))


async def get_replay_guard() -> JwtReplayGuard:
    redis = await get_redis()
    return JwtReplayGuard(redis)
```

- [ ] **Step 3: Implement app.py (skeleton)**

`document-viewer/src/document_viewer/api/app.py`:
```python
"""FastAPI application factory and `viewer-api` entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from document_viewer.shared.logging import configure_logging


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(level="INFO")
    yield


def create_app() -> FastAPI:
    from document_viewer.api.middleware import install_middleware
    from document_viewer.api.routes import embed, health, render

    app = FastAPI(title="document-viewer", lifespan=_lifespan)
    install_middleware(app)
    app.include_router(health.router)
    app.include_router(render.router)
    app.include_router(embed.router)
    return app


app = create_app()


def main() -> None:
    """Console-script entry: `viewer-api`."""
    import uvicorn

    uvicorn.run("document_viewer.api.app:app", host="0.0.0.0", port=8000, log_config=None)  # noqa: S104
```

- [ ] **Step 4: Commit**

```bash
git add src/document_viewer/api/__init__.py src/document_viewer/api/app.py src/document_viewer/api/deps.py
git commit -m "feat(api): FastAPI app skeleton and dependency providers"
```

---

### Task 23: Health routes (`/healthz`, `/readyz`)

**Files:**
- Create: `document-viewer/src/document_viewer/api/routes/__init__.py`
- Create: `document-viewer/src/document_viewer/api/routes/health.py`
- Create: `document-viewer/tests/unit/test_health_routes.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_health_routes.py`:
```python
"""Unit tests for the health routes."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from document_viewer.api.routes.health import router


def test_healthz_returns_200() -> None:
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_health_routes.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement health.py**

`document-viewer/src/document_viewer/api/routes/__init__.py`:
```python
"""HTTP route modules."""
```

`document-viewer/src/document_viewer/api/routes/health.py`:
```python
"""Liveness and readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
import redis.asyncio as redis_async

from document_viewer.api.deps import get_redis

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(redis: redis_async.Redis = Depends(get_redis)) -> dict[str, str]:
    pong = await redis.ping()
    return {"status": "ok" if pong else "degraded"}
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_health_routes.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/api/routes/__init__.py src/document_viewer/api/routes/health.py tests/unit/test_health_routes.py
git commit -m "feat(api): /healthz and /readyz endpoints"
```

---

### Task 24: `/render/{jwt}/manifest` route

**Files:**
- Create: `document-viewer/src/document_viewer/api/routes/render.py`
- Create: `document-viewer/tests/unit/test_render_routes.py`

- [ ] **Step 1: Write the failing manifest test**

`document-viewer/tests/unit/test_render_routes.py`:
```python
"""Unit tests for the /render routes."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from document_viewer.api.deps import get_arq_pool, get_jwt_verifier, get_replay_guard, get_settings
from document_viewer.api.routes.render import router
from document_viewer.shared.config import Settings
from document_viewer.shared.jwt_auth import JwtVerifier


SECRET = "test-secret"


def _token(**overrides: object) -> str:
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


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)

    settings = Settings(
        jwt_algorithm="HS256", jwt_hmac_secret=SECRET, redis_url="redis://x",
        source_backend="fs", jwt_required_iss="back-office",
    )
    arq = MagicMock()
    arq.enqueue_job = AsyncMock(return_value=MagicMock(
        result=AsyncMock(return_value={"mime": "application/pdf", "pages": 3, "dims": [{"w": 595, "h": 842}] * 3, "etag": "sha256:abc"})
    ))
    replay = MagicMock()
    replay.claim = AsyncMock(return_value=None)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_jwt_verifier] = lambda: JwtVerifier(algorithm="HS256", hmac_secret=SECRET, required_iss="back-office")
    app.dependency_overrides[get_arq_pool] = lambda: arq
    app.dependency_overrides[get_replay_guard] = lambda: replay
    return TestClient(app)


def test_manifest_returns_200_and_no_store(client: TestClient) -> None:
    r = client.get(f"/render/{_token()}/manifest")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-store"
    assert r.json()["pages"] == 3


def test_manifest_rejects_bad_jwt(client: TestClient) -> None:
    r = client.get("/render/not-a-jwt/manifest")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_render_routes.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement render.py (manifest only)**

`document-viewer/src/document_viewer/api/routes/render.py`:
```python
"""/render routes: manifest and page."""
from __future__ import annotations

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Response

from document_viewer.api.deps import get_arq_pool, get_jwt_verifier, get_replay_guard, get_settings
from document_viewer.shared.config import Settings
from document_viewer.shared.jwt_auth import (
    JwtClaims, JwtReplayGuard, JwtVerifier,
    TokenExpired, TokenInvalid, TokenReplayed,
)

router = APIRouter(prefix="/render")


async def _claims(jwt: str, verifier: JwtVerifier, replay: JwtReplayGuard) -> JwtClaims:
    try:
        claims = verifier.verify(jwt)
    except TokenExpired as e:
        raise HTTPException(status_code=401, detail="token expired") from e
    except TokenInvalid as e:
        raise HTTPException(status_code=401, detail="token invalid") from e
    try:
        await replay.claim(claims)
    except TokenReplayed as e:
        raise HTTPException(status_code=401, detail="token replayed") from e
    return claims


@router.get("/{jwt}/manifest")
async def manifest(
    jwt: str,
    response: Response,
    settings: Settings = Depends(get_settings),
    verifier: JwtVerifier = Depends(get_jwt_verifier),
    replay: JwtReplayGuard = Depends(get_replay_guard),
    arq: ArqRedis = Depends(get_arq_pool),
) -> dict[str, object]:
    claims = await _claims(jwt, verifier, replay)
    watermark = f"{claims.sub} · {claims.case}"
    job = await arq.enqueue_job(
        "render_manifest",
        obj=claims.obj, sub=claims.sub, case=claims.case, jti=claims.jti, watermark_text=watermark,
    )
    payload = await job.result(timeout=settings.render_timeout_seconds)
    response.headers["Cache-Control"] = "no-store"
    return {**payload, "ttl_seconds": settings.cache_ttl_seconds}
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_render_routes.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/api/routes/render.py tests/unit/test_render_routes.py
git commit -m "feat(api): /render/{jwt}/manifest endpoint with JWT verify + arq dispatch"
```

---

### Task 25: `/render/{jwt}/page/{n}` route

**Files:**
- Modify: `document-viewer/src/document_viewer/api/routes/render.py`
- Modify: `document-viewer/tests/unit/test_render_routes.py`

- [ ] **Step 1: Append failing page test**

In `document-viewer/tests/unit/test_render_routes.py`, append:
```python
def test_page_returns_webp_and_no_store(client: TestClient) -> None:
    arq = client.app.dependency_overrides[get_arq_pool]()
    arq.enqueue_job = AsyncMock(return_value=MagicMock(result=AsyncMock(return_value=b"RIFF\x00\x00\x00\x00WEBPVP8 ")))
    r = client.get(f"/render/{_token()}/page/1?w=800")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "image/webp"
    assert r.headers["Cache-Control"] == "no-store"
    assert r.content.startswith(b"RIFF")


def test_page_caps_width(client: TestClient) -> None:
    arq = client.app.dependency_overrides[get_arq_pool]()
    captured: dict[str, object] = {}
    async def _enqueue(name: str, **kwargs: object):  # noqa: ANN401
        captured.update(kwargs)
        return MagicMock(result=AsyncMock(return_value=b"RIFF\x00\x00\x00\x00WEBPVP8 "))
    arq.enqueue_job = AsyncMock(side_effect=_enqueue)
    client.get(f"/render/{_token()}/page/1?w=99999")
    assert captured["width"] <= 2400
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_render_routes.py -v
```
Expected: 2 new failures.

- [ ] **Step 3: Append page endpoint**

In `document-viewer/src/document_viewer/api/routes/render.py`, append:
```python
@router.get("/{jwt}/page/{n}")
async def page(
    jwt: str,
    n: int,
    w: int = 1200,
    settings: Settings = Depends(get_settings),
    verifier: JwtVerifier = Depends(get_jwt_verifier),
    replay: JwtReplayGuard = Depends(get_replay_guard),
    arq: ArqRedis = Depends(get_arq_pool),
) -> Response:
    claims = await _claims(jwt, verifier, replay)
    width = min(max(1, w), settings.max_page_width)
    watermark = f"{claims.sub} · {claims.case}"
    job = await arq.enqueue_job(
        "render_page",
        obj=claims.obj, sub=claims.sub, case=claims.case, jti=claims.jti,
        page=n, width=width, watermark_text=watermark,
    )
    webp = await job.result(timeout=settings.render_timeout_seconds)
    return Response(content=webp, media_type="image/webp", headers={"Cache-Control": "no-store"})
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_render_routes.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/api/routes/render.py tests/unit/test_render_routes.py
git commit -m "feat(api): /render/{jwt}/page/{n} with width cap and no-store"
```

---

### Task 26: Embed shell route + static HTML+JS

**Files:**
- Create: `document-viewer/src/document_viewer/api/routes/embed.py`
- Create: `document-viewer/services/embed/index.html`
- Create: `document-viewer/services/embed/main.js`
- Create: `document-viewer/tests/unit/test_embed_route.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_embed_route.py`:
```python
"""Unit tests for the /embed route."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from document_viewer.api.routes.embed import router


def test_embed_returns_html_with_main_js() -> None:
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).get("/embed/some-jwt")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("text/html")
    assert b"<!DOCTYPE html>" in r.content
    assert b"main.js" in r.content
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_embed_route.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create static shell files**

`document-viewer/services/embed/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>document-viewer</title>
  <style>
    html, body { margin: 0; background: #1f1f23; color: #e7e7ea; font-family: system-ui, sans-serif; }
    header { padding: 8px 12px; background: #2a2a30; display: flex; gap: 12px; align-items: center; }
    #pages { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 12px; }
    .page { max-width: 100%; box-shadow: 0 2px 12px rgba(0,0,0,.4); background: white; }
    button { background: #3a3a44; color: inherit; border: 0; padding: 6px 10px; border-radius: 4px; cursor: pointer; }
    #status { margin-left: auto; opacity: .7; font-size: 13px; }
  </style>
</head>
<body>
  <header>
    <button id="zoom-out">−</button>
    <button id="zoom-in">+</button>
    <span id="status">loading…</span>
  </header>
  <div id="pages"></div>
  <script src="/embed/main.js" data-token="__JWT__"></script>
</body>
</html>
```

`document-viewer/services/embed/main.js` (uses `replaceChildren()` to clear, avoiding any innerHTML write of untrusted data):
```javascript
(() => {
  const script = document.currentScript;
  const token = script.dataset.token;
  const pagesEl = document.getElementById("pages");
  const status = document.getElementById("status");
  let width = 1200;

  async function load() {
    status.textContent = "loading…";
    pagesEl.replaceChildren();
    const manifest = await fetch(`/render/${encodeURIComponent(token)}/manifest`).then(r => {
      if (!r.ok) throw new Error(`manifest ${r.status}`);
      return r.json();
    });
    for (let p = 1; p <= manifest.pages; p++) {
      const img = document.createElement("img");
      img.className = "page";
      img.loading = "lazy";
      img.src = `/render/${encodeURIComponent(token)}/page/${p}?w=${width}`;
      pagesEl.appendChild(img);
    }
    status.textContent = `${manifest.pages} pages`;
  }

  document.getElementById("zoom-in").onclick = () => { width = Math.min(width + 200, 2400); load(); };
  document.getElementById("zoom-out").onclick = () => { width = Math.max(width - 200, 400); load(); };

  load().catch(e => { status.textContent = `error: ${e.message}`; });
})();
```

- [ ] **Step 4: Implement embed.py**

`document-viewer/src/document_viewer/api/routes/embed.py`:
```python
"""Optional embeddable HTML+JS shell."""
from __future__ import annotations

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
    # jwt comes from URL path; escape into the HTML template by JSON-encoding via a data attribute
    import json as _json
    safe_token = _json.dumps(jwt)[1:-1]  # strip surrounding quotes
    html = _read("index.html").replace("__JWT__", safe_token)
    return Response(content=html, media_type="text/html")
```

- [ ] **Step 5: Run to verify pass**

```bash
pytest tests/unit/test_embed_route.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/document_viewer/api/routes/embed.py services/embed/ tests/unit/test_embed_route.py
git commit -m "feat(api): /embed/{jwt} static HTML+JS shell"
```

---

### Task 27: Request-ID middleware + uniform error envelope

**Files:**
- Create: `document-viewer/src/document_viewer/api/middleware.py`
- Create: `document-viewer/tests/unit/test_middleware.py`

- [ ] **Step 1: Write the failing test**

`document-viewer/tests/unit/test_middleware.py`:
```python
"""Unit tests for request-id middleware and error envelope."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from document_viewer.api.middleware import install_middleware


def _app() -> FastAPI:
    app = FastAPI()
    install_middleware(app)

    @app.get("/ok")
    def _ok() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/boom")
    def _boom() -> dict[str, str]:
        raise HTTPException(status_code=415, detail="bad mime")

    return app


def test_adds_request_id_header() -> None:
    r = TestClient(_app()).get("/ok")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")


def test_error_body_has_request_id() -> None:
    r = TestClient(_app()).get("/boom")
    assert r.status_code == 415
    body = r.json()
    assert body["error"] == "bad mime"
    assert body["request_id"]
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/unit/test_middleware.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement middleware.py**

`document-viewer/src/document_viewer/api/middleware.py`:
```python
"""HTTP middleware: request IDs, uniform error envelope."""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        resp: Response = await call_next(request)
        resp.headers["X-Request-ID"] = rid
        return resp


def install_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(HTTPException)
    async def _http_exc(request: Request, exc: HTTPException) -> Response:
        rid = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "request_id": rid},
            headers={"X-Request-ID": rid, "Cache-Control": "no-store"},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> Response:
        rid = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=500,
            content={"error": "internal error", "request_id": rid},
            headers={"X-Request-ID": rid, "Cache-Control": "no-store"},
        )
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/unit/test_middleware.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/document_viewer/api/middleware.py tests/unit/test_middleware.py
git commit -m "feat(api): request-id middleware + uniform error envelope"
```

---

## Phase 5 — Containerization

### Task 28: `.env.example`

**Files:**
- Create: `document-viewer/.env.example`

- [ ] **Step 1: Write the file**

`document-viewer/.env.example`:
```dotenv
# Auth — pick HS256 (HMAC) or RS256 (RSA public key)
JWT_ALGORITHM=HS256
JWT_HMAC_SECRET=change-me-to-a-long-random-secret
# JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----..."
JWT_REQUIRED_ISS=back-office

# Redis
REDIS_URL=redis://redis:6379/0

# Source backend (s3 or fs)
SOURCE_BACKEND=s3
S3_ENDPOINT=http://minio:9000
S3_BUCKET=kyc-docs
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=minio-user
S3_SECRET_ACCESS_KEY=minio-password
# FS_ROOT=/srv/docs

# Worker
GOTENBERG_URL=http://gotenberg:3000
WORKER_CONCURRENCY=4

# Limits
MAX_SOURCE_BYTES=104857600
MAX_PAGES=500
MAX_PAGE_WIDTH=2400
RENDER_TIMEOUT_SECONDS=30
OFFICE_TIMEOUT_SECONDS=60

# Cache
CACHE_TTL_SECONDS=900

# Watermark
WATERMARK_OPACITY=0.18
WATERMARK_FONT_SIZE=24
WATERMARK_ANGLE=-30
WATERMARK_COLOR=#808080
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: add .env.example documenting every supported variable"
```

---

### Task 29: Dockerfiles for api and worker

**Files:**
- Create: `document-viewer/services/api/Dockerfile`
- Create: `document-viewer/services/worker/Dockerfile`

- [ ] **Step 1: Create API Dockerfile**

`document-viewer/services/api/Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS build
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

FROM base AS runtime
WORKDIR /app
RUN groupadd -r app && useradd -r -g app -d /app app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin/viewer-api /usr/local/bin/viewer-api
COPY services/embed /app/services/embed
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"
CMD ["viewer-api"]
```

- [ ] **Step 2: Create Worker Dockerfile**

`document-viewer/services/worker/Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

FROM base AS build
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

FROM base AS runtime
WORKDIR /app
RUN groupadd -r app && useradd -r -g app -d /app app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin/viewer-worker /usr/local/bin/viewer-worker
USER app
CMD ["viewer-worker"]
```

- [ ] **Step 3: Verify both build**

```bash
docker build -f services/api/Dockerfile -t document-viewer-api:dev .
docker build -f services/worker/Dockerfile -t document-viewer-worker:dev .
```

Expected: both succeed.

- [ ] **Step 4: Commit**

```bash
git add services/api/Dockerfile services/worker/Dockerfile
git commit -m "build: multi-stage Dockerfiles for api and worker (non-root, healthcheck)"
```

---

### Task 30: `compose.yaml` (prod-shape) + `compose.test.yaml` (integration)

**Files:**
- Create: `document-viewer/compose.yaml`
- Create: `document-viewer/compose.test.yaml`

- [ ] **Step 1: Create `compose.yaml`**

`document-viewer/compose.yaml`:
```yaml
name: document-viewer

x-defaults: &svc
  restart: unless-stopped
  cap_drop: [ALL]
  security_opt:
    - "no-new-privileges:true"

networks:
  ingress:
  internal:
    internal: true

services:
  api:
    <<: *svc
    build:
      context: .
      dockerfile: services/api/Dockerfile
    env_file: .env
    networks: [ingress, internal]
    ports: ["8000:8000"]
    depends_on:
      redis:
        condition: service_healthy

  worker:
    <<: *svc
    build:
      context: .
      dockerfile: services/worker/Dockerfile
    env_file: .env
    networks: [internal]
    depends_on:
      redis: { condition: service_healthy }
      gotenberg: { condition: service_started }

  gotenberg:
    <<: *svc
    image: gotenberg/gotenberg:8@sha256:CHANGE-ME-TO-DIGEST
    networks: [internal]
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=512m
    mem_limit: 1.5g
    cpus: 1.5

  redis:
    <<: *svc
    image: redis:7-alpine
    networks: [internal]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

> **Note on digest pinning:** before opening the first PR, run `docker buildx imagetools inspect gotenberg/gotenberg:8 | grep Digest` and replace `CHANGE-ME-TO-DIGEST` with the result. Update on each Gotenberg release.

- [ ] **Step 2: Create `compose.test.yaml`**

`document-viewer/compose.test.yaml`:
```yaml
name: document-viewer-test

services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio-user
      MINIO_ROOT_PASSWORD: minio-password
    ports: ["9000:9000", "9001:9001"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 3s
      timeout: 2s
      retries: 10

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 2s
      retries: 10

  gotenberg:
    image: gotenberg/gotenberg:8
    ports: ["3000:3000"]

  api:
    build: { context: ., dockerfile: services/api/Dockerfile }
    environment:
      JWT_ALGORITHM: HS256
      JWT_HMAC_SECRET: test-secret
      JWT_REQUIRED_ISS: back-office
      REDIS_URL: redis://redis:6379/0
      SOURCE_BACKEND: s3
      S3_ENDPOINT: http://minio:9000
      S3_BUCKET: kyc-docs
      S3_REGION: us-east-1
      S3_ACCESS_KEY_ID: minio-user
      S3_SECRET_ACCESS_KEY: minio-password
      GOTENBERG_URL: http://gotenberg:3000
    ports: ["8000:8000"]
    depends_on:
      redis: { condition: service_healthy }
      minio: { condition: service_healthy }
      gotenberg: { condition: service_started }

  worker:
    build: { context: ., dockerfile: services/worker/Dockerfile }
    environment:
      JWT_ALGORITHM: HS256
      JWT_HMAC_SECRET: test-secret
      REDIS_URL: redis://redis:6379/0
      SOURCE_BACKEND: s3
      S3_ENDPOINT: http://minio:9000
      S3_BUCKET: kyc-docs
      S3_REGION: us-east-1
      S3_ACCESS_KEY_ID: minio-user
      S3_SECRET_ACCESS_KEY: minio-password
      GOTENBERG_URL: http://gotenberg:3000
    depends_on:
      redis: { condition: service_healthy }
      minio: { condition: service_healthy }
      gotenberg: { condition: service_started }
```

- [ ] **Step 3: Verify both parse**

```bash
docker compose -f compose.yaml config > /dev/null
docker compose -f compose.test.yaml config > /dev/null
```
Expected: no output (both valid).

- [ ] **Step 4: Commit**

```bash
git add compose.yaml compose.test.yaml
git commit -m "build: compose.yaml (prod) and compose.test.yaml (integration)"
```

---

### Task 31: Release + SBOM CI workflows

**Files:**
- Create: `document-viewer/.github/workflows/release.yml`
- Create: `document-viewer/.github/workflows/sbom.yml`

- [ ] **Step 1: Create release workflow**

`document-viewer/.github/workflows/release.yml`:
```yaml
name: Release

on:
  push:
    tags: ["v*"]

permissions:
  contents: read
  packages: write
  id-token: write

jobs:
  images:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: document-viewer } }
    strategy:
      matrix:
        service: [api, worker]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/metadata-action@v5
        id: meta
        with:
          images: ghcr.io/${{ github.repository }}-${{ matrix.service }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
      - uses: docker/build-push-action@v6
        with:
          context: document-viewer
          file: document-viewer/services/${{ matrix.service }}/Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          provenance: true
          sbom: true
      - uses: sigstore/cosign-installer@v3
      - run: cosign sign --yes ghcr.io/${{ github.repository }}-${{ matrix.service }}@${{ steps.build.outputs.digest }}
```

- [ ] **Step 2: Create SBOM workflow**

`document-viewer/.github/workflows/sbom.yml`:
```yaml
name: SBOM

on:
  release:
    types: [published]

jobs:
  sbom:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: document-viewer } }
    steps:
      - uses: actions/checkout@v4
      - uses: anchore/sbom-action@v0
        with:
          format: spdx-json
          output-file: sbom.spdx.json
          path: document-viewer
      - uses: softprops/action-gh-release@v2
        with:
          files: document-viewer/sbom.spdx.json
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml .github/workflows/sbom.yml
git commit -m "ci: container release + cosign signing + SBOM generation"
```

---

## Phase 6 — Helm Chart

### Task 32: Helm chart skeleton (Chart.yaml, values, _helpers)

**Files:**
- Create: `document-viewer/helm/document-viewer/Chart.yaml`
- Create: `document-viewer/helm/document-viewer/values.yaml`
- Create: `document-viewer/helm/document-viewer/values.example.yaml`
- Create: `document-viewer/helm/document-viewer/templates/_helpers.tpl`

- [ ] **Step 1: Chart.yaml**

```yaml
apiVersion: v2
name: document-viewer
description: Safe document renderer for KYC/AML
type: application
version: 0.1.0
appVersion: "0.1.0"
home: https://github.com/OWNER/document-viewer
sources: [https://github.com/OWNER/document-viewer]
maintainers:
  - name: Jimmi Hested
```

- [ ] **Step 2: values.yaml**

```yaml
image:
  registry: ghcr.io
  repository: OWNER/document-viewer
  tag: "0.1.0"
  pullPolicy: IfNotPresent

api:
  replicas: 2
  resources:
    requests: { cpu: 100m, memory: 256Mi }
    limits:   { cpu: 1000m, memory: 1Gi }
  service: { type: ClusterIP, port: 8000 }
  ingress:
    enabled: true
    className: nginx
    host: viewer.example.com
    tls: true

worker:
  replicas: 3
  concurrency: 4
  resources:
    requests: { cpu: 250m, memory: 512Mi }
    limits:   { cpu: 2000m, memory: 2Gi }
  autoscaling:
    enabled: false
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70

gotenberg:
  image: gotenberg/gotenberg:8@sha256:CHANGE-ME
  replicas: 2
  resources:
    requests: { cpu: 500m, memory: 1Gi }
    limits:   { cpu: 2000m, memory: 2Gi }

redis:
  embedded: true
  image: redis:7-alpine

config:
  jwtAlgorithm: RS256
  jwtRequiredIss: back-office
  sourceBackend: s3
  s3Endpoint: ""
  s3Bucket: ""
  s3Region: us-east-1
  cacheTtlSeconds: 900
  maxSourceBytes: 104857600
  maxPages: 500
  maxPageWidth: 2400

secrets:
  jwtPublicKey: ""
  s3AccessKeyId: ""
  s3SecretAccessKey: ""

monitoring:
  serviceMonitor:
    enabled: false
    namespace: monitoring
    interval: 30s
```

- [ ] **Step 3: values.example.yaml**

Copy `values.yaml` and add commentary; left as a doc artifact.

- [ ] **Step 4: _helpers.tpl**

`document-viewer/helm/document-viewer/templates/_helpers.tpl`:
```yaml
{{- define "viewer.labels" -}}
app.kubernetes.io/name: document-viewer
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "viewer.apiImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.repository }}-api:{{ .Values.image.tag }}
{{- end -}}

{{- define "viewer.workerImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.repository }}-worker:{{ .Values.image.tag }}
{{- end -}}
```

- [ ] **Step 5: Verify**

```bash
helm lint helm/document-viewer
```
Expected: `0 chart(s) failed`.

- [ ] **Step 6: Commit**

```bash
git add helm/document-viewer/Chart.yaml helm/document-viewer/values.yaml \
        helm/document-viewer/values.example.yaml helm/document-viewer/templates/_helpers.tpl
git commit -m "feat(helm): chart skeleton (Chart.yaml, values, helpers)"
```

---

### Task 33: Helm — api Deployment, Service, Ingress

**Files:**
- Create: `document-viewer/helm/document-viewer/templates/api-deployment.yaml`
- Create: `document-viewer/helm/document-viewer/templates/api-service.yaml`
- Create: `document-viewer/helm/document-viewer/templates/api-ingress.yaml`

- [ ] **Step 1: api-deployment.yaml**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-api
  labels: { {{- include "viewer.labels" . | nindent 4 }} }
spec:
  replicas: {{ .Values.api.replicas }}
  selector: { matchLabels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: api } }
  template:
    metadata:
      labels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: api }
    spec:
      securityContext: { runAsNonRoot: true, runAsUser: 1000, fsGroup: 1000 }
      containers:
        - name: api
          image: {{ include "viewer.apiImage" . | quote }}
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports: [{ containerPort: 8000 }]
          securityContext:
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          env:
            - { name: REDIS_URL, value: redis://{{ .Release.Name }}-redis:6379/0 }
          envFrom:
            - configMapRef: { name: {{ .Release.Name }}-config }
            - secretRef:    { name: {{ .Release.Name }}-secrets }
          livenessProbe:  { httpGet: { path: /healthz, port: 8000 }, periodSeconds: 10 }
          readinessProbe: { httpGet: { path: /readyz,  port: 8000 }, periodSeconds: 5 }
          resources: {{- toYaml .Values.api.resources | nindent 12 }}
```

- [ ] **Step 2: api-service.yaml**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-api
  labels: { {{- include "viewer.labels" . | nindent 4 }} }
spec:
  type: {{ .Values.api.service.type }}
  ports: [{ port: {{ .Values.api.service.port }}, targetPort: 8000, name: http }]
  selector: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: api }
```

- [ ] **Step 3: api-ingress.yaml**

```yaml
{{- if .Values.api.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ .Release.Name }}-api
  labels: { {{- include "viewer.labels" . | nindent 4 }} }
spec:
  ingressClassName: {{ .Values.api.ingress.className }}
  rules:
    - host: {{ .Values.api.ingress.host }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend: { service: { name: {{ .Release.Name }}-api, port: { number: {{ .Values.api.service.port }} } } }
  {{- if .Values.api.ingress.tls }}
  tls:
    - hosts: [{{ .Values.api.ingress.host }}]
      secretName: {{ .Release.Name }}-api-tls
  {{- end }}
{{- end }}
```

- [ ] **Step 4: Verify template renders**

```bash
helm template document-viewer ./helm/document-viewer > /tmp/rendered.yaml
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add helm/document-viewer/templates/api-deployment.yaml \
        helm/document-viewer/templates/api-service.yaml \
        helm/document-viewer/templates/api-ingress.yaml
git commit -m "feat(helm): api Deployment, Service, Ingress with hardened securityContext"
```

---

### Task 34: Helm — worker Deployment

**Files:**
- Create: `document-viewer/helm/document-viewer/templates/worker-deployment.yaml`

- [ ] **Step 1: worker-deployment.yaml**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-worker
  labels: { {{- include "viewer.labels" . | nindent 4 }} }
spec:
  replicas: {{ .Values.worker.replicas }}
  selector: { matchLabels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: worker } }
  template:
    metadata:
      labels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: worker }
    spec:
      securityContext: { runAsNonRoot: true, runAsUser: 1000, fsGroup: 1000 }
      containers:
        - name: worker
          image: {{ include "viewer.workerImage" . | quote }}
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          securityContext:
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          env:
            - { name: REDIS_URL, value: redis://{{ .Release.Name }}-redis:6379/0 }
            - { name: GOTENBERG_URL, value: http://{{ .Release.Name }}-gotenberg:3000 }
            - { name: WORKER_CONCURRENCY, value: {{ .Values.worker.concurrency | quote }} }
          envFrom:
            - configMapRef: { name: {{ .Release.Name }}-config }
            - secretRef:    { name: {{ .Release.Name }}-secrets }
          resources: {{- toYaml .Values.worker.resources | nindent 12 }}
```

- [ ] **Step 2: Verify**

```bash
helm template document-viewer ./helm/document-viewer > /tmp/rendered.yaml
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add helm/document-viewer/templates/worker-deployment.yaml
git commit -m "feat(helm): worker Deployment with hardened securityContext"
```

---

### Task 35: Helm — gotenberg Deployment + Service + NetworkPolicy + Redis

**Files:**
- Create: `document-viewer/helm/document-viewer/templates/gotenberg-deployment.yaml`
- Create: `document-viewer/helm/document-viewer/templates/gotenberg-service.yaml`
- Create: `document-viewer/helm/document-viewer/templates/gotenberg-networkpolicy.yaml`
- Create: `document-viewer/helm/document-viewer/templates/redis.yaml`

- [ ] **Step 1: gotenberg-deployment.yaml**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-gotenberg
  labels: { {{- include "viewer.labels" . | nindent 4 }} }
spec:
  replicas: {{ .Values.gotenberg.replicas }}
  selector: { matchLabels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: gotenberg } }
  template:
    metadata:
      labels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: gotenberg }
    spec:
      securityContext: { runAsNonRoot: true, runAsUser: 1001, fsGroup: 1001 }
      containers:
        - name: gotenberg
          image: {{ .Values.gotenberg.image | quote }}
          ports: [{ containerPort: 3000 }]
          securityContext:
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          volumeMounts: [{ name: tmp, mountPath: /tmp }]
          resources: {{- toYaml .Values.gotenberg.resources | nindent 12 }}
      volumes: [{ name: tmp, emptyDir: { medium: Memory, sizeLimit: 512Mi } }]
```

- [ ] **Step 2: gotenberg-service.yaml**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-gotenberg
  labels: { {{- include "viewer.labels" . | nindent 4 }} }
spec:
  type: ClusterIP
  ports: [{ port: 3000, targetPort: 3000, name: http }]
  selector: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: gotenberg }
```

- [ ] **Step 3: gotenberg-networkpolicy.yaml**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ .Release.Name }}-gotenberg
  labels: { {{- include "viewer.labels" . | nindent 4 }} }
spec:
  podSelector:
    matchLabels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: gotenberg }
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: worker }
      ports: [{ protocol: TCP, port: 3000 }]
  # No egress rules ⇒ default-deny egress.
  egress: []
```

- [ ] **Step 4: redis.yaml (embedded option)**

```yaml
{{- if .Values.redis.embedded }}
apiVersion: apps/v1
kind: Deployment
metadata: { name: {{ .Release.Name }}-redis }
spec:
  replicas: 1
  selector: { matchLabels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: redis } }
  template:
    metadata:
      labels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: redis }
    spec:
      containers:
        - name: redis
          image: {{ .Values.redis.image | quote }}
          ports: [{ containerPort: 6379 }]
---
apiVersion: v1
kind: Service
metadata: { name: {{ .Release.Name }}-redis }
spec:
  ports: [{ port: 6379, targetPort: 6379 }]
  selector: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: redis }
{{- end }}
```

- [ ] **Step 5: Verify**

```bash
helm template document-viewer ./helm/document-viewer | kubectl apply --dry-run=client -f -
```
Expected: all resources `(dry run) configured/created`.

- [ ] **Step 6: Commit**

```bash
git add helm/document-viewer/templates/gotenberg-*.yaml helm/document-viewer/templates/redis.yaml
git commit -m "feat(helm): gotenberg Deployment/Service + NetworkPolicy denying egress + Redis"
```

---

### Task 36: Helm — ConfigMap, Secret, HPA, ServiceMonitor

**Files:**
- Create: `document-viewer/helm/document-viewer/templates/configmap.yaml`
- Create: `document-viewer/helm/document-viewer/templates/secret.yaml`
- Create: `document-viewer/helm/document-viewer/templates/hpa.yaml`
- Create: `document-viewer/helm/document-viewer/templates/servicemonitor.yaml`

- [ ] **Step 1: configmap.yaml**

```yaml
apiVersion: v1
kind: ConfigMap
metadata: { name: {{ .Release.Name }}-config }
data:
  JWT_ALGORITHM: {{ .Values.config.jwtAlgorithm | quote }}
  JWT_REQUIRED_ISS: {{ .Values.config.jwtRequiredIss | quote }}
  SOURCE_BACKEND: {{ .Values.config.sourceBackend | quote }}
  S3_ENDPOINT: {{ .Values.config.s3Endpoint | quote }}
  S3_BUCKET: {{ .Values.config.s3Bucket | quote }}
  S3_REGION: {{ .Values.config.s3Region | quote }}
  CACHE_TTL_SECONDS: {{ .Values.config.cacheTtlSeconds | quote }}
  MAX_SOURCE_BYTES: {{ .Values.config.maxSourceBytes | quote }}
  MAX_PAGES: {{ .Values.config.maxPages | quote }}
  MAX_PAGE_WIDTH: {{ .Values.config.maxPageWidth | quote }}
```

- [ ] **Step 2: secret.yaml**

```yaml
apiVersion: v1
kind: Secret
metadata: { name: {{ .Release.Name }}-secrets }
type: Opaque
stringData:
  JWT_PUBLIC_KEY: {{ .Values.secrets.jwtPublicKey | quote }}
  S3_ACCESS_KEY_ID: {{ .Values.secrets.s3AccessKeyId | quote }}
  S3_SECRET_ACCESS_KEY: {{ .Values.secrets.s3SecretAccessKey | quote }}
```

- [ ] **Step 3: hpa.yaml**

```yaml
{{- if .Values.worker.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: {{ .Release.Name }}-worker }
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: {{ .Release.Name }}-worker }
  minReplicas: {{ .Values.worker.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.worker.autoscaling.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: {{ .Values.worker.autoscaling.targetCPUUtilizationPercentage }} }
{{- end }}
```

- [ ] **Step 4: servicemonitor.yaml**

```yaml
{{- if .Values.monitoring.serviceMonitor.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ .Release.Name }}-api
  namespace: {{ .Values.monitoring.serviceMonitor.namespace }}
spec:
  endpoints: [{ port: http, interval: {{ .Values.monitoring.serviceMonitor.interval }}, path: /metrics }]
  selector:
    matchLabels: { app.kubernetes.io/name: document-viewer, app.kubernetes.io/component: api }
  namespaceSelector: { any: true }
{{- end }}
```

- [ ] **Step 5: Verify**

```bash
helm lint helm/document-viewer
helm template document-viewer ./helm/document-viewer > /tmp/rendered.yaml
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add helm/document-viewer/templates/configmap.yaml \
        helm/document-viewer/templates/secret.yaml \
        helm/document-viewer/templates/hpa.yaml \
        helm/document-viewer/templates/servicemonitor.yaml
git commit -m "feat(helm): ConfigMap, Secret, optional HPA and ServiceMonitor"
```

---

## Phase 7 — Integration Tests

### Task 37: Integration conftest (MinIO seed, JWT signer, client)

**Files:**
- Create: `document-viewer/tests/integration/__init__.py`
- Create: `document-viewer/tests/integration/conftest.py`

- [ ] **Step 1: Create integration package**

```bash
touch tests/integration/__init__.py
```

- [ ] **Step 2: Create conftest**

`document-viewer/tests/integration/conftest.py`:
```python
"""Integration fixtures. Assumes compose.test.yaml is already up."""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import boto3
import httpx
import jwt as pyjwt
import pytest

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_KEY = os.getenv("S3_ACCESS_KEY_ID", "minio-user")
S3_SECRET = os.getenv("S3_SECRET_ACCESS_KEY", "minio-password")
BUCKET = os.getenv("S3_BUCKET", "kyc-docs")
JWT_SECRET = os.getenv("JWT_HMAC_SECRET", "test-secret")


@pytest.fixture(scope="session", autouse=True)
def _ensure_bucket() -> None:
    s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_KEY, aws_secret_access_key=S3_SECRET)
    try:
        s3.head_bucket(Bucket=BUCKET)
    except Exception:
        s3.create_bucket(Bucket=BUCKET)


@pytest.fixture()
def upload_fixture():  # type: ignore[no-untyped-def]
    def _u(key: str, src: Path) -> None:
        s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_KEY, aws_secret_access_key=S3_SECRET)
        s3.put_object(Bucket=BUCKET, Key=key, Body=src.read_bytes())
    return _u


@pytest.fixture()
def make_token():  # type: ignore[no-untyped-def]
    def _t(obj: str, *, sub: str = "alice@bank.com", case: str = "case-1", ttl: int = 60) -> str:
        return pyjwt.encode(
            {"iss": "back-office", "sub": sub, "obj": obj, "case": case,
             "iat": int(time.time()), "exp": int(time.time()) + ttl, "jti": uuid.uuid4().hex},
            JWT_SECRET, algorithm="HS256",
        )
    return _t


@pytest.fixture()
def client() -> httpx.Client:
    return httpx.Client(base_url=API_BASE, timeout=60)
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/__init__.py tests/integration/conftest.py
git commit -m "test(integration): conftest for compose-driven end-to-end tests"
```

---

### Task 38: E2E PDF rendering

**Files:**
- Create: `document-viewer/tests/integration/test_e2e_pdf.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end: PDF source → manifest → page render."""
from __future__ import annotations

from pathlib import Path

import httpx

FIXTURE = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


def test_pdf_manifest_and_first_page(upload_fixture, make_token, client: httpx.Client) -> None:  # type: ignore[no-untyped-def]
    key = "e2e/simple.pdf"
    upload_fixture(key, FIXTURE)
    token = make_token(key)

    m = client.get(f"/render/{token}/manifest")
    assert m.status_code == 200, m.text
    assert m.headers["cache-control"] == "no-store"
    body = m.json()
    assert body["pages"] == 3
    assert body["mime"] == "application/pdf"

    p = client.get(f"/render/{make_token(key)}/page/1?w=800")
    assert p.status_code == 200
    assert p.headers["content-type"] == "image/webp"
    assert p.content[:4] == b"RIFF"
```

- [ ] **Step 2: Run via compose.test.yaml**

```bash
docker compose -f compose.test.yaml up -d --wait
pytest tests/integration/test_e2e_pdf.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_e2e_pdf.py
git commit -m "test(integration): e2e PDF manifest + page render"
```

---

### Task 39: E2E DOCX rendering via Gotenberg

**Files:**
- Create: `document-viewer/tests/fixtures/_make_docx.py`
- Create: `document-viewer/tests/fixtures/simple.docx`
- Create: `document-viewer/tests/integration/test_e2e_docx.py`

- [ ] **Step 1: Build DOCX fixture**

`document-viewer/tests/fixtures/_make_docx.py`:
```python
"""Generate a small docx via python-docx for integration tests."""
from pathlib import Path

from docx import Document  # add `python-docx` to [dev] deps for this fixture only

doc = Document()
doc.add_heading("Hello", level=1)
doc.add_paragraph("This is page one of the test document.")
doc.add_page_break()
doc.add_paragraph("Second page.")
doc.save(Path(__file__).parent / "simple.docx")
```

Add `python-docx>=1.1` to `[project.optional-dependencies].dev`. Run:
```bash
pip install -e ".[dev]"
python tests/fixtures/_make_docx.py
```

- [ ] **Step 2: Write the test**

`document-viewer/tests/integration/test_e2e_docx.py`:
```python
"""End-to-end: docx → Gotenberg → pikepdf → pypdfium2 → WebP."""
from __future__ import annotations

from pathlib import Path

import httpx

FIXTURE = Path(__file__).parent.parent / "fixtures" / "simple.docx"


def test_docx_round_trip(upload_fixture, make_token, client: httpx.Client) -> None:  # type: ignore[no-untyped-def]
    key = "e2e/simple.docx"
    upload_fixture(key, FIXTURE)
    token = make_token(key)

    m = client.get(f"/render/{token}/manifest")
    assert m.status_code == 200
    body = m.json()
    assert body["pages"] >= 1
    assert "wordprocessingml" in body["mime"]

    p = client.get(f"/render/{make_token(key)}/page/1?w=800")
    assert p.status_code == 200
    assert p.content[:4] == b"RIFF"
```

- [ ] **Step 3: Run**

```bash
pytest tests/integration/test_e2e_docx.py -v
```
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/_make_docx.py tests/fixtures/simple.docx tests/integration/test_e2e_docx.py pyproject.toml
git commit -m "test(integration): e2e DOCX through Gotenberg"
```

---

### Task 40: E2E image rendering

**Files:**
- Create: `document-viewer/tests/integration/test_e2e_image.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end: PNG/JPEG source → WebP page."""
from __future__ import annotations

import io
from pathlib import Path

import httpx
from PIL import Image


def test_jpeg_renders_single_page(tmp_path: Path, upload_fixture, make_token, client: httpx.Client) -> None:  # type: ignore[no-untyped-def]
    img = Image.new("RGB", (1600, 1200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    f = tmp_path / "img.jpg"
    f.write_bytes(buf.getvalue())
    upload_fixture("e2e/img.jpg", f)

    token = make_token("e2e/img.jpg")
    m = client.get(f"/render/{token}/manifest")
    assert m.status_code == 200
    assert m.json()["pages"] == 1
    p = client.get(f"/render/{make_token('e2e/img.jpg')}/page/1?w=800")
    assert p.status_code == 200
    assert p.content[:4] == b"RIFF"
```

- [ ] **Step 2: Run + commit**

```bash
pytest tests/integration/test_e2e_image.py -v
git add tests/integration/test_e2e_image.py
git commit -m "test(integration): e2e image rendering"
```

---

### Task 41: E2E cache behavior

**Files:**
- Create: `document-viewer/tests/integration/test_e2e_cache.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end: second page request hits cache (faster + same bytes)."""
from __future__ import annotations

import time
from pathlib import Path

import httpx

FIXTURE = Path(__file__).parent.parent / "fixtures" / "simple.pdf"


def test_second_page_request_is_cached(upload_fixture, make_token, client: httpx.Client) -> None:  # type: ignore[no-untyped-def]
    upload_fixture("e2e/cache.pdf", FIXTURE)

    t1 = make_token("e2e/cache.pdf", sub="alice")
    t2 = make_token("e2e/cache.pdf", sub="alice")

    s1 = time.perf_counter()
    r1 = client.get(f"/render/{t1}/page/1?w=800")
    d1 = time.perf_counter() - s1
    assert r1.status_code == 200

    s2 = time.perf_counter()
    r2 = client.get(f"/render/{t2}/page/1?w=800")
    d2 = time.perf_counter() - s2
    assert r2.status_code == 200
    assert r1.content == r2.content
    # Cached request should be at least 3x faster
    assert d2 * 3 < d1 + 0.01
```

- [ ] **Step 2: Run + commit**

```bash
pytest tests/integration/test_e2e_cache.py -v
git add tests/integration/test_e2e_cache.py
git commit -m "test(integration): per-user cache hit returns identical bytes faster"
```

---

### Task 42: E2E auth (expired, replayed, wrong-iss)

**Files:**
- Create: `document-viewer/tests/integration/test_e2e_auth.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end auth checks: expired, replayed, wrong issuer."""
from __future__ import annotations

import time

import httpx
import jwt as pyjwt


def test_expired_token_401(make_token, client: httpx.Client) -> None:  # type: ignore[no-untyped-def]
    expired = pyjwt.encode(
        {"iss": "back-office", "sub": "x", "obj": "kyc/x.pdf", "case": "c", "jti": "j",
         "iat": int(time.time()) - 600, "exp": int(time.time()) - 60},
        "test-secret", algorithm="HS256",
    )
    r = client.get(f"/render/{expired}/manifest")
    assert r.status_code == 401


def test_replayed_token_401(upload_fixture, make_token, client: httpx.Client) -> None:  # type: ignore[no-untyped-def]
    from pathlib import Path
    upload_fixture("e2e/replay.pdf", Path(__file__).parent.parent / "fixtures" / "simple.pdf")
    token = make_token("e2e/replay.pdf")
    r1 = client.get(f"/render/{token}/manifest")
    assert r1.status_code == 200
    r2 = client.get(f"/render/{token}/manifest")
    assert r2.status_code == 401


def test_wrong_iss_401(client: httpx.Client) -> None:
    bad = pyjwt.encode(
        {"iss": "evil", "sub": "x", "obj": "kyc/x.pdf", "case": "c", "jti": "j",
         "iat": int(time.time()), "exp": int(time.time()) + 60},
        "test-secret", algorithm="HS256",
    )
    r = client.get(f"/render/{bad}/manifest")
    assert r.status_code == 401
```

- [ ] **Step 2: Run + commit**

```bash
pytest tests/integration/test_e2e_auth.py -v
git add tests/integration/test_e2e_auth.py
git commit -m "test(integration): expired/replayed/wrong-iss tokens return 401"
```

---

## Phase 8 — Security Regression Corpus

### Task 43: Security corpus + tests

**Files:**
- Create: `document-viewer/tests/security_corpus/__init__.py`
- Create: `document-viewer/tests/security_corpus/README.md`
- Create: `document-viewer/tests/security_corpus/_build_corpus.py`
- Create: `document-viewer/tests/security_corpus/pdfs/*` (built by script)
- Create: `document-viewer/tests/security_corpus/images/*` (built by script)
- Create: `document-viewer/tests/security_corpus/test_corpus.py`

- [ ] **Step 1: README explaining the corpus**

`document-viewer/tests/security_corpus/README.md`:
```markdown
# Security Regression Corpus

Each fixture in this folder is intentionally malformed or contains a payload that some PDF/office parser has historically failed on. For every fixture the test must pass one of:

- A rendered WebP image is returned (parser handled the input safely).
- A documented error code is returned (415, 413, 500-with-request-id, etc.).

What must NOT happen:
- The worker permanently crashes (after one job all subsequent jobs fail).
- Source bytes appear in any response body.
- The pikepdf clean step misses a `/JavaScript`, `/EmbeddedFile`, `/OpenAction`, or `/Launch` entry.

Build the corpus with `python tests/security_corpus/_build_corpus.py`.
```

- [ ] **Step 2: Corpus builder**

`document-viewer/tests/security_corpus/_build_corpus.py`:
```python
"""Build the corpus. Run once; outputs are committed."""
from pathlib import Path
import struct

import pikepdf
from PIL import Image

ROOT = Path(__file__).parent

(ROOT / "pdfs").mkdir(exist_ok=True)
(ROOT / "images").mkdir(exist_ok=True)

# 1. PDF with /JavaScript and /OpenAction
p = pikepdf.Pdf.new()
p.add_blank_page(page_size=(595, 842))
p.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS="bad()")
p.save(ROOT / "pdfs" / "with_js.pdf")

# 2. PDF with /Launch action
p = pikepdf.Pdf.new()
p.add_blank_page(page_size=(595, 842))
p.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.Launch, F="/bin/sh")
p.save(ROOT / "pdfs" / "with_launch.pdf")

# 3. Truncated PDF
data = (ROOT.parent / "fixtures" / "simple.pdf").read_bytes()
(ROOT / "pdfs" / "truncated.pdf").write_bytes(data[: len(data) // 2])

# 4. Decompression bomb PNG (huge declared dimensions, tiny IDAT)
def _png_bomb() -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">II BBBBB", 60000, 60000, 8, 2, 0, 0, 0)
    crc = __import__("binascii").crc32(b"IHDR" + ihdr) & 0xFFFFFFFF
    return sig + struct.pack(">I", 13) + b"IHDR" + ihdr + struct.pack(">I", crc) + b"\x00\x00\x00\x00IEND\xaeB`\x82"

(ROOT / "images" / "decompression_bomb.png").write_bytes(_png_bomb())

# 5. PE labeled .pdf (magic must reject before parsing)
(ROOT / "pdfs" / "pe_labelled_pdf.pdf").write_bytes(b"MZ\x90\x00" + b"\x00" * 1024)

print("corpus built")
```

Run:
```bash
python tests/security_corpus/_build_corpus.py
```

- [ ] **Step 3: Write the corpus tests**

`document-viewer/tests/security_corpus/test_corpus.py`:
```python
"""Each corpus fixture must either render safely or return a documented error."""
from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pytest

from document_viewer.render.pdf_clean import clean_pdf
from document_viewer.shared.mime import MimeNotAllowed, detect_mime

CORPUS = Path(__file__).parent


def test_pikepdf_strips_js() -> None:
    raw = (CORPUS / "pdfs" / "with_js.pdf").read_bytes()
    cleaned = clean_pdf(raw)
    p = pikepdf.open(io.BytesIO(cleaned))
    assert "/OpenAction" not in p.Root.keys()


def test_pikepdf_strips_launch() -> None:
    raw = (CORPUS / "pdfs" / "with_launch.pdf").read_bytes()
    cleaned = clean_pdf(raw)
    p = pikepdf.open(io.BytesIO(cleaned))
    assert "/OpenAction" not in p.Root.keys()


def test_truncated_pdf_raises_cleanly() -> None:
    raw = (CORPUS / "pdfs" / "truncated.pdf").read_bytes()
    with pytest.raises(Exception):  # pikepdf raises ; pipeline returns 500 with request id  # noqa: BLE001
        clean_pdf(raw)


def test_pe_labelled_pdf_rejected_by_magic() -> None:
    raw = (CORPUS / "pdfs" / "pe_labelled_pdf.pdf").read_bytes()
    with pytest.raises(MimeNotAllowed):
        detect_mime(raw[:4096], allowed=["application/pdf"])


def test_decompression_bomb_image_rejected_or_capped() -> None:
    from PIL import Image, UnidentifiedImageError

    raw = (CORPUS / "images" / "decompression_bomb.png").read_bytes()
    with pytest.raises((Image.DecompressionBombError, UnidentifiedImageError, OSError)):
        Image.open(io.BytesIO(raw)).load()
```

- [ ] **Step 4: Run + commit**

```bash
pytest tests/security_corpus -v
git add tests/security_corpus/
git commit -m "test(security): corpus of malformed/dangerous files + clean-or-reject assertions"
```

---

## Phase 9 — Documentation

### Task 44: Getting-started docs

**Files:**
- Create: `document-viewer/docs/index.md`
- Create: `document-viewer/docs/getting-started/quickstart.md`
- Create: `document-viewer/docs/getting-started/installation-compose.md`
- Create: `document-viewer/docs/getting-started/installation-helm.md`

- [ ] **Step 1: Write `docs/index.md`**

```markdown
# document-viewer

Safe document renderer for KYC/AML and other PII-sensitive workflows.

- **What it is:** [Architecture overview](architecture/overview.md)
- **Use it:** [Quickstart](getting-started/quickstart.md)
- **Integrate:** [JWT signing recipes](integration/issuing-tokens.md)
- **Ship to k8s:** [Helm chart](getting-started/installation-helm.md)
- **Operate:** [Configuration reference](operations/configuration.md)
- **Trust model:** [Threat model](security/threat-model.md) and [Known limitations](security/known-limitations.md)
```

- [ ] **Step 2: Write `docs/getting-started/quickstart.md`**

5-minute compose-up walkthrough. Include: clone, `.env`, `docker compose up`, upload a sample PDF to MinIO via `mc` or the web UI, mint a JWT with a one-liner Python script, open `/embed/<jwt>` in a browser.

(Provide complete shell commands and the one-liner; do not assume the reader knows mc.)

- [ ] **Step 3: Write `docs/getting-started/installation-compose.md`**

Detailed: prerequisites, env var explanation, choosing between built-in Redis and an external one, how to point at an existing MinIO/Ceph, how to wire nginx in front for TLS termination.

- [ ] **Step 4: Write `docs/getting-started/installation-helm.md`**

Detailed: prerequisites (k8s 1.27+, ingress controller, optional cert-manager), `helm install` invocation, sample `values.yaml`, NetworkPolicy compatibility note, how to verify the deployment.

- [ ] **Step 5: Commit**

```bash
git add docs/index.md docs/getting-started/
git commit -m "docs: index + getting-started (quickstart, compose, helm)"
```

---

### Task 45: Architecture docs

**Files:**
- Create: `document-viewer/docs/architecture/overview.md`
- Create: `document-viewer/docs/architecture/data-flow.md`
- Create: `document-viewer/docs/architecture/component-reference.md`

- [ ] **Step 1: overview.md** — distilled architecture diagram + 1–2 paragraph narrative per container. Mirror §3 of the design spec but reader-facing.

- [ ] **Step 2: data-flow.md** — sequence of a single page render: ingress → JWT verify → cache check → enqueue → worker → source fetch → mime detect → pipeline → cache write → response. Include an ASCII or mermaid sequence diagram.

- [ ] **Step 3: component-reference.md** — table of every module in `src/document_viewer/`, one line each, linked to the source path.

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/
git commit -m "docs: architecture overview, data flow, component reference"
```

---

### Task 46: API + integration docs

**Files:**
- Create: `document-viewer/docs/api/reference.md`
- Create: `document-viewer/docs/api/jwt.md`
- Create: `document-viewer/docs/integration/issuing-tokens.md`
- Create: `document-viewer/docs/integration/embedding.md`
- Create: `document-viewer/docs/integration/examples/python.md`
- Create: `document-viewer/docs/integration/examples/nodejs.md`

- [ ] **Step 1: api/reference.md** — every endpoint: path, params, response, errors. Pull from §4 of the design spec.

- [ ] **Step 2: api/jwt.md** — full claim format, RS256 key generation example, HS256 secret rotation guidance.

- [ ] **Step 3: integration/issuing-tokens.md** — sample server-side JWT-signing code in Python and Node (use the real libraries: `PyJWT`, `jsonwebtoken`).

- [ ] **Step 4: integration/embedding.md** — three patterns: bare `<img>`, the `/embed/<jwt>` iframe, and a custom JS loop hitting `/manifest`+`/page`. Working snippets.

- [ ] **Step 5: examples/python.md** and **examples/nodejs.md** — runnable scripts that issue a token, fetch the manifest, save page 1 to disk.

- [ ] **Step 6: Commit**

```bash
git add docs/api/ docs/integration/
git commit -m "docs: API reference, JWT format, integration examples (Python + Node)"
```

---

### Task 47: Operations docs

**Files:**
- Create: `document-viewer/docs/operations/configuration.md`
- Create: `document-viewer/docs/operations/deployment-compose.md`
- Create: `document-viewer/docs/operations/deployment-helm.md`
- Create: `document-viewer/docs/operations/monitoring.md`
- Create: `document-viewer/docs/operations/tuning.md`
- Create: `document-viewer/docs/operations/upgrades.md`

- [ ] **Step 1: configuration.md** — table of every env var with default, allowed range, and what tuning it.

- [ ] **Step 2: deployment-compose.md** and **deployment-helm.md** — operator runbooks. Cover backups (or "there's nothing to back up, by design"), log shipping, secrets rotation.

- [ ] **Step 3: monitoring.md** — what to log, suggested Prometheus alerts: high render p99, Redis memory, Gotenberg restart loop, worker queue backlog.

- [ ] **Step 4: tuning.md** — when to bump `WORKER_CONCURRENCY`, when to raise `MAX_PAGE_WIDTH`, cache hit ratio targets, expected CPU/RAM per concurrent render.

- [ ] **Step 5: upgrades.md** — compatibility matrix (chart version ↔ app version ↔ Gotenberg version). Breaking-change conventions (semver, deprecation cycles).

- [ ] **Step 6: Commit**

```bash
git add docs/operations/
git commit -m "docs: operations (config, deploy, monitoring, tuning, upgrades)"
```

---

### Task 48: Security docs

**Files:**
- Create: `document-viewer/docs/security/threat-model.md`
- Create: `document-viewer/docs/security/hardening.md`
- Create: `document-viewer/docs/security/disclosure.md`
- Create: `document-viewer/docs/security/known-limitations.md`

- [ ] **Step 1: threat-model.md** — STRIDE-ish table:
  - **Threats defended:** malicious PDF/office files (rendered in isolated worker; pikepdf strips actions before pypdfium2); PII bytes leaking via downloads (no original ever served); token replay (Redis SETNX with TTL); ingress-bypass-of-auth (api also validates).
  - **Threats not defended:** screenshot/screen-record; OS-level exfil; coerced employee with legitimate access; supply-chain attack on Gotenberg/PDFium/Pillow; DoS beyond rate limits + size caps.

- [ ] **Step 2: hardening.md** — prod checklist: rotate JWT secret quarterly, set `NetworkPolicy`, separate namespaces, audit log retention 90+ days, run as non-root, pull images by digest, scan with Trivy + CodeQL, restrict ingress to corporate VPN, etc.

- [ ] **Step 3: disclosure.md** — restate `SECURITY.md` timeline and add: CVE filing convention, credit-or-anonymity options, embargo length.

- [ ] **Step 4: known-limitations.md** — explicit honest list:
  - No protection against screenshots, screen recording, or photographing the monitor.
  - No protection against an employee with legitimate access exfiltrating to a personal channel.
  - No real-time DLP scanning of the document content.
  - PDF and office parsing surface (pikepdf + pypdfium2 + LibreOffice) is still parser code; vulnerabilities may exist.
  - No anti-tampering on the watermark (cropping multiple instances leaves at least one, but a determined attacker can manually edit the image).

- [ ] **Step 5: Commit**

```bash
git add docs/security/
git commit -m "docs: security — threat model, hardening, disclosure, known limitations"
```

---

### Task 49: Development docs

**Files:**
- Create: `document-viewer/docs/development/setup.md`
- Create: `document-viewer/docs/development/testing.md`
- Create: `document-viewer/docs/development/release-process.md`

- [ ] **Step 1: setup.md** — full local dev: Python venv, install with `.[dev]`, `libmagic1` apt install for Linux + brew for macOS, optional `pre-commit`.

- [ ] **Step 2: testing.md** — TDD discipline, fixture builders (`tests/fixtures/_make_*.py`), running unit vs integration vs corpus, how to add a new security fixture.

- [ ] **Step 3: release-process.md** — tag-driven, semver, what triggers cosign-signed image push, when to update Gotenberg digest pin.

- [ ] **Step 4: Commit**

```bash
git add docs/development/setup.md docs/development/testing.md docs/development/release-process.md
git commit -m "docs: development setup, testing approach, release process"
```

---

### Task 50: Architecture Decision Records (ADRs)

**Files:**
- Create: `document-viewer/docs/development/adr/README.md`
- Create: `document-viewer/docs/development/adr/0001-render-to-images-not-stream-pdf.md`
- Create: `document-viewer/docs/development/adr/0002-gotenberg-vs-bespoke-libreoffice.md`
- Create: `document-viewer/docs/development/adr/0003-pypdfium2-vs-pymupdf-licensing.md`
- Create: `document-viewer/docs/development/adr/0004-jwt-from-upstream-vs-internal-oidc.md`

- [ ] **Step 1: ADR index**

`document-viewer/docs/development/adr/README.md`:
```markdown
# Architecture Decision Records

We use [MADR](https://adr.github.io/madr/) for ADRs. Each file documents a load-bearing decision: the context, the options considered, the decision, and its consequences.

| # | Title | Status |
|---|---|---|
| 0001 | Render to images, not stream PDFs | Accepted |
| 0002 | Gotenberg vs bespoke LibreOffice container | Accepted |
| 0003 | pypdfium2 vs PyMuPDF (licensing) | Accepted |
| 0004 | JWT from upstream vs internal OIDC | Accepted |

## Adding an ADR

Copy the most recent ADR as a template. Number sequentially. Set `Status: Proposed` until reviewed; flip to `Accepted` once merged.
```

- [ ] **Step 2: Write each ADR** in MADR format. Each is ~150–300 words: Context (the problem), Decision drivers, Considered options, Decision, Consequences (good + bad).

  Pull substance from the brainstorming spec — each of these decisions is already documented there. Examples:
  - **0001** points back to the trade-off matrix you and Claude wrote.
  - **0002** explains the Gotenberg vs bespoke trade.
  - **0003** documents the AGPL → Apache-2.0 swap and links to `pyproject.toml`.
  - **0004** explains why the back-office mints JWTs rather than the viewer holding an OIDC session.

- [ ] **Step 3: Commit**

```bash
git add docs/development/adr/
git commit -m "docs(adr): 0001–0004 covering rendering, office, licensing, and auth decisions"
```

---

### Task 51: Move design spec to `docs/design/`

**Files:**
- Move: `document-viewer/docs/superpowers/specs/2026-05-20-document-viewer-design.md` → `document-viewer/docs/design/2026-05-20-document-viewer-design.md`
- Delete: `document-viewer/docs/superpowers/specs/` (and `docs/superpowers/plans/` if empty)

- [ ] **Step 1: Move the file**

```bash
mkdir -p docs/design
git mv docs/superpowers/specs/2026-05-20-document-viewer-design.md docs/design/2026-05-20-document-viewer-design.md
```

- [ ] **Step 2: Decide on plans/**

The implementation plan (`docs/superpowers/plans/2026-05-20-document-viewer.md`) is internal-tooling output. Two choices:

- **Leave it** under `docs/superpowers/plans/` for the lifetime of the build; remove from the repo when the implementation lands (or keep it forever as historical context).
- **Move it** to `docs/design/2026-05-20-document-viewer-plan.md` alongside the spec.

Decision: leave the plan in `docs/superpowers/plans/` during active implementation, then delete it once the final task lands. This keeps the public `docs/` tree clean.

- [ ] **Step 3: Update spec-internal cross-references**

The spec references `docs/superpowers/specs/` in §17. Update that to `docs/design/`.

```bash
sed -i 's|docs/superpowers/specs/|docs/design/|g' docs/design/2026-05-20-document-viewer-design.md
```

- [ ] **Step 4: Commit**

```bash
git add docs/design/ docs/superpowers/specs/ 2>/dev/null || true
git commit -m "docs: relocate design spec to docs/design/ (public-facing path)"
```

---

## Done

After Task 51, the repo contains a fully-implemented, fully-documented, TDD-built, MIT-licensed `document-viewer`. The `docs/superpowers/plans/2026-05-20-document-viewer.md` file can be deleted in a follow-up commit (or kept as historical record).

**Suggested final verification before announcing v0.1.0:**

```bash
cd document-viewer
ruff check . && ruff format --check . && mypy src/
pytest tests/unit -v
docker compose -f compose.test.yaml up -d --wait
pytest tests/integration -v
pytest tests/security_corpus -v
docker compose -f compose.test.yaml down -v
helm lint helm/document-viewer
helm template document-viewer ./helm/document-viewer | kubectl apply --dry-run=client -f -
```

All green ⇒ tag `v0.1.0`, the release workflow ships signed container images and an SBOM.






