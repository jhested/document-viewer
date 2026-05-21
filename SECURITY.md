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

See the [threat model](docs/security/threat-model.md) for what this project does and does not defend against.
