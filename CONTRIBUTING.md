# Contributing

Thanks for your interest. This project follows TDD — please write the failing test first.

## Local development

Requirements: Python 3.12+, Docker (or Podman) with Compose v2.

```bash
git clone https://github.com/jhested/document-viewer.git
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
