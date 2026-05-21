# Upgrades

The repository ships three things that version independently:

- The **application** (API + worker images), version equals the tag.
- The **Helm chart** (`helm/document-viewer/`), version in
  `Chart.yaml:version`.
- The **Gotenberg** image, pinned by digest in the chart and Compose file.

This document records the compatibility rules between them.

## Versioning

The application and the chart both follow [Semantic Versioning](https://semver.org/):

- **MAJOR** — breaking change. For the application this means a removed
  or renamed environment variable, a removed endpoint, or an incompatible
  change to the embed-token JWT format. For the chart this means a
  required values key was renamed, removed, or changed default in a way
  that breaks existing installs.
- **MINOR** — backward-compatible addition. New endpoints, new env vars
  with sensible defaults, new chart values that default to off.
- **PATCH** — backward-compatible fix. Bug fixes, security fixes,
  documentation, internal refactors.

The chart's `appVersion` tracks the application version it was tested
against. The chart `version` increments independently when only chart
content changes (e.g. a NetworkPolicy fix with no app change).

## Compatibility matrix

The following combinations are tested and supported. Newer chart minor
versions accept older app patch versions within the same minor band.

| Chart | App | Gotenberg | Notes |
|---|---|---|---|
| `0.1.x` | `0.1.x` | `gotenberg/gotenberg:8` (pin by digest) | Initial release. |

When a new release lands, this table will gain a row. Operators upgrading
across minor versions should consult both `CHANGELOG.md` (app) and
`helm/document-viewer/Chart.yaml` notes (chart).

## Gotenberg

Gotenberg is treated as an external dependency. The chart and Compose
file pin it by digest, not by tag. The pin must be updated explicitly:

- The placeholder `gotenberg/gotenberg:8@sha256:CHANGE-ME` (Helm) and
  `gotenberg/gotenberg:8@sha256:CHANGE-ME-TO-DIGEST` (Compose) must be
  replaced before deploying.
- Look up the digest with:
  ```bash
  docker buildx imagetools inspect gotenberg/gotenberg:8 \
    --format '{{json .Manifest.Digest}}'
  ```
- The application is tested against Gotenberg 8.x. Major version bumps
  of Gotenberg are not guaranteed compatible; they will be called out in
  the application release notes.

## Deprecation policy

Breaking changes are announced one minor version before they ship:

1. **Announce** in `CHANGELOG.md` for the minor release that introduces
   the new behavior or option, with the planned removal version.
2. **Mark deprecated**: log a warning at startup when a deprecated env
   var or values key is read, and document it as deprecated in
   `configuration.md` (this directory) and the chart's
   `values.example.yaml`.
3. **Remove** no earlier than the next major version, never inside a
   minor or patch.

Example (hypothetical): a future release that renames
`MAX_PAGE_WIDTH` → `MAX_RENDER_WIDTH` would announce the rename in the
`0.2.0` notes, accept either name in `0.2.x` with a startup warning for
the old name, and remove `MAX_PAGE_WIDTH` in `1.0.0`.

## Helm upgrade procedure

```bash
helm repo update                                    # if installing from a repo
helm upgrade document-viewer ./helm/document-viewer -f my-values.yaml
kubectl rollout status deploy/document-viewer-api
kubectl rollout status deploy/document-viewer-worker
kubectl rollout status deploy/document-viewer-gotenberg
```

Roll back if any rollout fails:

```bash
helm rollback document-viewer
kubectl rollout status deploy/document-viewer-api
```

For chart upgrades crossing a major version, diff the rendered manifests
first:

```bash
helm diff upgrade document-viewer ./helm/document-viewer -f my-values.yaml
```

(`helm diff` is the [helm-diff plugin](https://github.com/databus23/helm-diff)).

## Compose upgrade procedure

```bash
docker compose pull
docker compose up -d
```

Compose recreates only containers whose image digest changed. For chart-
or app-major upgrades, review `CHANGELOG.md` before pulling.

## Pre-upgrade checklist

Before any production upgrade:

- Read `CHANGELOG.md` between the current version and the target.
- Check the compatibility matrix above for chart/app/Gotenberg
  combinations.
- Confirm there are no deprecated env vars in your `.env` /
  `my-values.yaml` that will be removed by the target version.
- Have a rollback plan: previous chart values, previous image tag,
  previous Gotenberg digest.
