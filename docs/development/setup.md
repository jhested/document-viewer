# Development setup

This page walks through getting `document-viewer` running on a developer
laptop without Docker, so you can iterate quickly on the API or worker code.
For a containerised stack (suitable for production-shaped smoke tests), see
[`docs/getting-started/quickstart.md`](../getting-started/quickstart.md).

## Prerequisites

- Python 3.12 or newer. The project pins `requires-python = ">=3.12"` in
  [`pyproject.toml`](../../pyproject.toml).
- Redis 7 (only needed when running the worker or API locally). Either the
  `redis-server` binary, or `docker run --rm -p 6379:6379 redis:7-alpine`.
- A working `libmagic` install. `python-magic` (used by
  `src/document_viewer/shared/mime.py`) wraps the system library; it will
  not work without it.
- Optional: Gotenberg, if you intend to exercise the office rendering path
  end-to-end. `docker run --rm -p 3000:3000 gotenberg/gotenberg:8` is the
  shortest path.

### Installing `libmagic`

Debian / Ubuntu:

```bash
sudo apt install libmagic1
```

macOS (Homebrew):

```bash
brew install libmagic
```

If `python -c "import magic; magic.from_buffer(b'%PDF-1.4')"` raises
`ImportError: failed to find libmagic`, the system library is missing or
not on the loader path.

## Clone and create a virtualenv

```bash
git clone https://github.com/jhested/document-viewer.git
cd document-viewer
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
```

The `dev` extra is defined in
[`pyproject.toml`](../../pyproject.toml) under
`[project.optional-dependencies]` and pulls in `pytest`, `pytest-asyncio`,
`pytest-cov`, `pytest-httpx`, `moto`, `freezegun`, `ruff`, `mypy`,
`fakeredis`, `python-docx`, and `boto3`. After this, `ruff`, `mypy`, and
`pytest` should all resolve from `.venv/bin/`.

You can either activate the venv (`source .venv/bin/activate`) or call
binaries directly with the `.venv/bin/` prefix; this page uses the
explicit form for clarity.

## Environment file

The API and worker read configuration from environment variables
(see `src/document_viewer/shared/config.py`). For local development, copy
the example file:

```bash
cp .env.example .env
```

[`.env.example`](../../.env.example) is checked in and lists every
variable with sane defaults. The two values you may want to change for
local dev:

- `JWT_HMAC_SECRET` — must be at least 32 bytes. The placeholder will be
  rejected by the loader.
- `REDIS_URL` — set to `redis://localhost:6379/0` if you are running
  Redis directly on the host (the file ships with the docker-compose
  hostname).

The API and worker do not read `.env` themselves; export the variables
into your shell, or use a runner that does (for example
`uvicorn ... --env-file .env`). A quick way is:

```bash
set -a; source .env; set +a
```

## Optional: pre-commit hooks

The repository does not ship a `.pre-commit-config.yaml`, but `pre-commit`
itself plays nicely with the project's lint commands. If you want a
local hook that mirrors CI, install pre-commit (`pipx install pre-commit`
or `.venv/bin/pip install pre-commit`) and drop a config alongside the
repo:

```yaml
# .pre-commit-config.yaml (untracked; create locally if you want it)
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        args: ["--config-file", "mypy.ini"]
        additional_dependencies: ["types-redis", "types-Pillow"]
```

Then `pre-commit install`. CI runs `ruff check`, `ruff format --check`,
and `mypy --strict src/document_viewer` regardless, so this is purely a
local convenience.

## Running the API

Start a Redis instance (one of):

```bash
# Native binary
redis-server --port 6379

# Or a throwaway container
docker run --rm -p 6379:6379 redis:7-alpine
```

Then launch the API. The `viewer-api` console script is declared in
[`pyproject.toml`](../../pyproject.toml) under `[project.scripts]` and
maps to `document_viewer.api.app:main`:

```bash
.venv/bin/viewer-api
```

By default the API binds `0.0.0.0:8000`. Hit `http://localhost:8000/healthz`
to confirm it is up. Routes are defined under
`src/document_viewer/api/routes/`; see the OpenAPI surface at
`http://localhost:8000/docs`.

## Running the worker

The worker is an [`arq`](https://arq-docs.helpmanual.io/) consumer. The
`viewer-worker` console script maps to
`document_viewer.worker.settings:main`:

```bash
.venv/bin/viewer-worker
```

It connects to the same Redis as the API and waits for render jobs
enqueued by the API. To exercise the office path you also need Gotenberg
reachable at `GOTENBERG_URL` (default `http://gotenberg:3000` — override
to `http://localhost:3000` for native dev).

A typical local layout uses three terminals:

```text
term 1: redis-server --port 6379
term 2: docker run --rm -p 3000:3000 gotenberg/gotenberg:8
term 3: set -a; source .env; set +a
        .venv/bin/viewer-api   # in one tab
        .venv/bin/viewer-worker # in another tab
```

## Source-tree layout

- `src/document_viewer/api/` — FastAPI app, routes, middleware.
- `src/document_viewer/worker/` — arq settings and job entry points.
- `src/document_viewer/render/` — PDF cleaning, image pipeline, watermark.
- `src/document_viewer/shared/` — config, MIME detection, source backends
  (filesystem and S3), cache key derivation, JWT validation.
- `services/api/Dockerfile`, `services/worker/Dockerfile` — production
  container builds.
- `tests/` — three test trees (see
  [`docs/development/testing.md`](testing.md)).

## Next

- [Testing approach](testing.md) — TDD discipline, fixture builders, and
  how the three test trees are run.
- [Release process](release-process.md) — tagging, image signing, SBOM
  attachment, and when to bump the pinned Gotenberg digest.
