# Release process

Releases are tag-driven. Pushing an annotated `vX.Y.Z` tag builds and
signs the container images; cutting a GitHub Release on that tag
attaches an SPDX SBOM. There is no manual `docker push`, no manual
`cosign sign`, and no manual SBOM generation — all three are wired into
[`.github/workflows/release.yml`](../../.github/workflows/release.yml)
and [`.github/workflows/sbom.yml`](../../.github/workflows/sbom.yml).

## Versioning

The project follows [Semantic Versioning](https://semver.org/). The
single source of truth is the `version` field in
[`pyproject.toml`](../../pyproject.toml). Bump rules:

- **Patch (`vX.Y.Z+1`)** — backwards-compatible bug fixes, dependency
  bumps that do not change behaviour, documentation-only changes that
  are still worth tagging.
- **Minor (`vX.Y+1.0`)** — new endpoints, new configuration keys,
  additional supported MIME types, anything additive.
- **Major (`vX+1.0.0`)** — breaking API changes (endpoint shape, header
  contract, JWT claim semantics), changes to required configuration,
  removal of supported inputs.

While the project is pre-1.0 (`0.y.z`), bumps to `y` may include
breaking changes; document them prominently in the changelog.

## Cutting a release

1. **Make sure `main` is green.** All required CI checks
   (`ruff`, `mypy`, unit, integration, security corpus) must pass on the
   commit you intend to tag. Do not tag a commit that is failing CI.

2. **Bump the version in
   [`pyproject.toml`](../../pyproject.toml).**

   ```toml
   [project]
   name = "document-viewer"
   version = "0.2.0"
   ```

3. **Update
   [`CHANGELOG.md`](../../CHANGELOG.md).** Move entries out of
   `## [Unreleased]` into a new dated section that matches the version
   you are about to tag. The convention is
   [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):

   ```markdown
   ## [0.2.0] - 2026-05-21

   ### Added
   - ...

   ### Changed
   - ...

   ### Fixed
   - ...
   ```

4. **Commit and push the bump.**

   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "release: 0.2.0"
   git push origin main
   ```

5. **Tag the commit and push the tag.** Annotated tags only — the
   release workflow's `docker/metadata-action` reads the tag name to
   derive image tags via `type=semver`.

   ```bash
   git tag -a v0.2.0 -m "v0.2.0"
   git push origin v0.2.0
   ```

   Pushing the tag triggers
   [`.github/workflows/release.yml`](../../.github/workflows/release.yml).
   It runs once per service (matrix over `api` and `worker`) and for
   each:

   - Builds the image from `services/${service}/Dockerfile`.
   - Pushes it to `ghcr.io/${repo}-${service}` with the tags
     `X.Y.Z` and `X.Y` (per the `docker/metadata-action` config).
   - Attaches build provenance and an SBOM to the image via BuildKit.
   - Installs cosign and signs the resulting digest using GitHub OIDC
     (`cosign sign --yes "${IMAGE}@${DIGEST}"`).

   The workflow requires `id-token: write` permission so cosign can use
   the keyless OIDC flow against Sigstore. No private key is stored in
   the repository.

6. **Cut the GitHub Release.** Create a release from the tag in the
   GitHub UI (or with `gh release create v0.2.0 --notes-from-tag`).
   Publishing the release fires
   [`.github/workflows/sbom.yml`](../../.github/workflows/sbom.yml),
   which generates an SPDX-JSON SBOM with `anchore/sbom-action` and
   uploads `sbom.spdx.json` as a release asset via
   `softprops/action-gh-release`.

7. **Verify after the fact.** Confirm the artifacts exist:

   ```bash
   # Images and tags
   docker buildx imagetools inspect ghcr.io/jhested/document-viewer-api:0.2.0
   docker buildx imagetools inspect ghcr.io/jhested/document-viewer-worker:0.2.0

   # Cosign signature on the digest
   cosign verify \
     --certificate-identity-regexp "https://github.com/jhested/document-viewer" \
     --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
     ghcr.io/jhested/document-viewer-api:0.2.0

   # SBOM attached to the release
   gh release view v0.2.0 --json assets --jq '.assets[].name'
   ```

If any step fails after the tag has been pushed, delete the tag
(`git push --delete origin v0.2.0 && git tag -d v0.2.0`), fix forward,
and tag the new commit with the same version. Never reuse a published
tag for different artifacts.

## When to bump the pinned Gotenberg digest

Production [`compose.yaml`](../../compose.yaml) pins Gotenberg by digest
so the office rendering path is reproducible and auditable:

```yaml
gotenberg:
  image: gotenberg/gotenberg:8@sha256:CHANGE-ME-TO-DIGEST
```

The Helm chart pins the same image. Bump the pin every time Gotenberg
publishes a new `8.x` release — typically once per upstream release.
Track upstream at
[github.com/gotenberg/gotenberg/releases](https://github.com/gotenberg/gotenberg/releases).

Procedure:

1. Resolve the current digest of the `:8` tag:

   ```bash
   docker buildx imagetools inspect gotenberg/gotenberg:8 | grep Digest
   ```

   The output line looks like
   `Digest: sha256:ab12cd...`. Copy the full `sha256:` value.

2. Update [`compose.yaml`](../../compose.yaml) and the equivalent
   reference in `helm/document-viewer/` so they match. The string after
   `@` is the new digest.

3. Run the integration suite against the new image:

   ```bash
   docker compose -f compose.test.yaml up -d --wait
   .venv/bin/pytest -m integration tests/integration
   docker compose -f compose.test.yaml down -v
   ```

   `compose.test.yaml` floats on the `:8` tag, so a passing integration
   run on the new tag confirms the digest you just pinned still works
   end-to-end.

4. Commit the digest bump on its own PR with a clear title (for
   example `chore(deps): bump Gotenberg 8 digest`) and merge it. The
   next release will then ship the new pin.

Do not couple a Gotenberg digest bump with an unrelated feature change —
if the office path regresses, you want a single small commit to bisect
against.
