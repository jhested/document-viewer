# Testing

`document-viewer` is developed test-first. Every change — new feature,
bug fix, refactor — begins with a failing test that pins the desired
behaviour. Only once the test fails for the right reason do we write the
minimal implementation to turn it green. This is the project convention,
not a suggestion: PRs that ship implementation without tests will be
asked to add them.

The repository is structured around three independent test trees with
different cost profiles and different things they prove. Use the right
one for the change you are making.

## The three trees

| Tree | Location | What it proves | Cost |
|---|---|---|---|
| Unit | [`tests/unit/`](../../tests/unit/) | A single module behaves correctly in isolation. | Milliseconds. No external services. |
| Integration | [`tests/integration/`](../../tests/integration/) | API + worker + Redis + MinIO + Gotenberg agree end-to-end. | Tens of seconds. Needs `compose.test.yaml`. |
| Security corpus | [`tests/security_corpus/`](../../tests/security_corpus/) | Hostile inputs render safely or are rejected with a documented error — never crash the worker. | Sub-second once corpus is built. |

### `pytest.ini_options`

The marker discipline lives in
[`pyproject.toml`](../../pyproject.toml):

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = ["error"]
markers = [
    "integration: end-to-end tests that need compose.test.yaml services",
]
addopts = "-m 'not integration'"
```

Two consequences worth knowing:

- `filterwarnings = ["error"]` — any warning becomes a test failure.
  If a dependency raises a deprecation warning we have not handled, the
  test fails. Fix the call site rather than silencing the warning.
- `addopts = "-m 'not integration'"` — a bare `pytest` invocation skips
  the integration tree by default, so you can run unit + corpus tests
  without any Docker setup.

## Running unit tests

The fast path:

```bash
.venv/bin/pytest
```

This runs every test under `tests/` that is not marked `integration` —
in practice, that means the unit tree and the security corpus. Add `-v`
for verbose output, `-x` to stop on first failure, or
`--cov=src/document_viewer` for coverage (the coverage source is
configured in
[`pyproject.toml`](../../pyproject.toml)).

To run a single module:

```bash
.venv/bin/pytest tests/unit/test_pdf_clean.py -v
```

## Running integration tests

Integration tests live in [`tests/integration/`](../../tests/integration/)
and are auto-tagged with the `integration` marker by
[`tests/integration/conftest.py`](../../tests/integration/conftest.py).
That fixture also asserts the MinIO bucket exists and provides helpers
to upload fixtures and mint JWTs.

The stack they need is described in
[`compose.test.yaml`](../../compose.test.yaml): MinIO + Redis + Gotenberg
+ a built `api` + a built `worker`. Spin it up, run the suite, tear it
down:

```bash
docker compose -f compose.test.yaml up -d --wait
.venv/bin/pytest -m integration tests/integration
docker compose -f compose.test.yaml down -v
```

The `--wait` flag blocks `up` until every healthcheck reports healthy,
which avoids the classic "test ran before MinIO accepted connections"
flake.

Environment variables read by the fixtures (`API_BASE`, `S3_ENDPOINT`,
`S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`,
`JWT_HMAC_SECRET`) default to the values baked into `compose.test.yaml`.
Override them in your shell if you point the suite at a different stack.

## Running the security corpus

The corpus is a small set of intentionally hostile fixtures committed
under [`tests/security_corpus/pdfs/`](../../tests/security_corpus/pdfs/)
and [`tests/security_corpus/images/`](../../tests/security_corpus/images/).
A bare `pytest` already includes
[`tests/security_corpus/`](../../tests/security_corpus/) because the
tests are not marked `integration`:

```bash
.venv/bin/pytest tests/security_corpus -v
```

If you need to regenerate the corpus (for example after adding a new
fixture), run the builder once:

```bash
.venv/bin/python tests/security_corpus/_build_corpus.py
```

The output binaries are committed alongside the test code, so the
builder only needs to run when the corpus itself changes. See
[`tests/security_corpus/README.md`](../../tests/security_corpus/README.md)
for the assertion contract: each fixture must either render safely or
raise a documented error; the worker must not crash.

## Fixture builders

The general-purpose fixtures live under
[`tests/fixtures/`](../../tests/fixtures/). Each `_make_*.py` is a
one-shot script: run it once, commit the binary it produces.

- [`_make_simple_pdf.py`](../../tests/fixtures/_make_simple_pdf.py) —
  builds `tests/fixtures/simple.pdf`, a three-page Letter-sized empty
  PDF used by renderer tests.
- [`_make_pdf_with_js.py`](../../tests/fixtures/_make_pdf_with_js.py) —
  builds `tests/fixtures/pdf_with_js.pdf` with an `/OpenAction
  /JavaScript` entry and a Names tree pointing at another JavaScript
  action. Used to assert `clean_pdf` strips both.
- [`_make_docx.py`](../../tests/fixtures/_make_docx.py) — builds
  `tests/fixtures/simple.docx` via `python-docx`. The dependency is
  already in the `dev` extra in
  [`pyproject.toml`](../../pyproject.toml), so a single
  `python tests/fixtures/_make_docx.py` (after `pip install -e '.[dev]'`)
  is enough. Used by integration tests for the Office path.

Run a builder from the repository root, for example:

```bash
.venv/bin/python tests/fixtures/_make_simple_pdf.py
```

Each script prints the path it wrote. Commit the generated file in the
same PR that adds the test consuming it — reviewers should never have
to rebuild fixtures locally to verify a change.

## Adding a new security corpus fixture

The corpus is intentionally small and grows when we find a class of
hostile input we are not yet covering. Adding one is four steps:

1. **Add a builder branch in
   [`tests/security_corpus/_build_corpus.py`](../../tests/security_corpus/_build_corpus.py).**
   Follow the existing numbering comments (`# 1.`, `# 2.`, ...). Write
   the bytes to `pdfs/`, `images/`, or whichever subdirectory matches
   the format. Prefer building the bytes deterministically over checking
   in a binary from an outside source; reviewers should be able to
   recreate it.
2. **Add a test in
   [`tests/security_corpus/test_corpus.py`](../../tests/security_corpus/test_corpus.py).**
   The assertion must pin one of the two acceptable outcomes:
   - The pipeline produces a safe output (for example, `clean_pdf` strips
     the offending entry — see `test_pikepdf_strips_js`).
   - The pipeline raises a documented exception (for example,
     `MimeNotAllowed`, `pikepdf.PdfError`, or
     `PIL.Image.DecompressionBombError`).
   What is _not_ acceptable: the test passing because the call silently
   succeeded on hostile input.
3. **Run the builder once and commit the result.**

   ```bash
   .venv/bin/python tests/security_corpus/_build_corpus.py
   git add tests/security_corpus/pdfs/your_new_fixture.pdf
   git add tests/security_corpus/_build_corpus.py
   git add tests/security_corpus/test_corpus.py
   ```

4. **Run the corpus.**

   ```bash
   .venv/bin/pytest tests/security_corpus -v
   ```

If the new test passes _before_ the implementation change, the assertion
is too weak — strengthen it until it fails, then write the fix.

## Linting and type-checking

These run on every CI build and should run on every developer machine
before pushing. Configuration lives in
[`ruff.toml`](../../ruff.toml) and [`mypy.ini`](../../mypy.ini).

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/document_viewer
```

`mypy` is configured with `strict = true`. New code that needs an
exception should add a narrow `ignore_missing_imports` block in
`mypy.ini`, not a per-line `# type: ignore`.
