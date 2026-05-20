# Security Regression Corpus

Each fixture in this folder is intentionally malformed or contains a payload that some PDF/office parser has historically failed on. For every fixture the test must pass one of:

- A rendered WebP image is returned (parser handled the input safely).
- A documented error code is returned (415, 413, 500-with-request-id, etc.).

What must NOT happen:
- The worker permanently crashes (after one job all subsequent jobs fail).
- Source bytes appear in any response body.
- The pikepdf clean step misses a `/JavaScript`, `/EmbeddedFile`, `/OpenAction`, or `/Launch` entry.

Build the corpus with `python tests/security_corpus/_build_corpus.py`.
