# Known limitations

This document is the honest list. If you are evaluating `document-viewer` for
a KYC/AML deployment, read this first — before the README, before the threat
model, before the marketing. The bullet points below are things this project
does **not** do and never will, in their current form.

If any of these are a deal-breaker for your environment, that is fine and
expected. Mitigations live elsewhere: in your endpoint management, your
network egress controls, your hiring and offboarding processes, and your
SIEM. This project deliberately picks a narrow scope and stays inside it.

## What this project does not protect against

### 1. Screenshots, screen recording, and photographs of the monitor

By design. Once a watermarked page is rendered into the user's browser, it
exists as pixels on their screen. There is no DRM, no HDCP, no agent on the
endpoint that disables print-screen or blanks the window when an external
camera is detected. A user with a phone can photograph the monitor; an
endpoint with screen-record permissions can capture the session.

**The watermark is a deterrent and a forensic trail, not a hard control.**
The user's identifier (`sub`) and case (`case`) are baked into the image and
tiled across the page; if a screenshot leaks, the watermark identifies who
rendered it. That is the limit of the protection.

Mitigations live in endpoint management: MDM that disables screen recording,
DLP on the workstation, physical controls on the workspace.

### 2. Exfiltration by an employee with legitimate access

If a user is authorised to view a document and they decide to leak it to a
personal channel — pasting the screenshot into a private chat, holding up
their phone, dictating the contents — `document-viewer` cannot stop them. The
JWT-gated, watermarked, no-download design **correctly** rendered the page
for an **authorised** user.

This is a people-and-process problem. Mitigations: user and entity behaviour
analytics (UEBA), DLP at the network egress, audit-log review of `sub` +
`case` access patterns, separation of duties, and the everyday HR controls
that govern access to PII.

### 3. Real-time DLP scanning of document content

The service does not look at *what is in* the document for the purpose of
classifying or blocking. It renders. If a document contains data that should
not be visible to a given user, the back-office must catch that before
issuing the JWT — by deciding not to issue one, or by issuing one scoped to
a different (redacted) object.

If you need content-aware DLP, put a DLP appliance between the user's
browser and the wider internet, or pre-process documents in the back-office
to redact before they land on the source store.

### 4. Parser vulnerabilities in pikepdf, pypdfium2, LibreOffice, Pillow, or libmagic

We sanitise PDFs with pikepdf before pypdfium2 sees them, run office files in
an isolated, egress-denied Gotenberg pod, and enforce a strict mime allowlist
with libmagic — and **the underlying parsers are still parser code written
in C/C++**. New CVEs land in these projects with predictable regularity.

What we do:

- Pin Gotenberg, PDFium, Pillow, pikepdf, and libmagic versions explicitly.
- Run CodeQL on our Python on every PR and weekly.
- Subscribe to upstream security advisories and re-pin promptly when CVEs
  affect them.
- Run the parser stack as `runAsNonRoot`, `readOnlyRootFilesystem`,
  `capabilities.drop: [ALL]`, with NetworkPolicy denying egress from
  Gotenberg.

What we **cannot** do:

- Detect a 0-day in any of these parsers before it is disclosed.
- Catch a supply-chain compromise of an upstream package on the day it
  ships.

The defence is depth: even if pikepdf misses an obfuscation, the
NetworkPolicy means a compromised Gotenberg cannot phone home. Even if
LibreOffice is exploited, the container has no capabilities, a read-only
root, and no egress. The blast radius is bounded; the existence of the bug
is not prevented.

### 5. Watermark removal by a determined attacker

The watermark is tiled across the page at multiple positions, so a single
crop leaves other instances visible. But a determined attacker with an image
editor — or, increasingly, with a content-aware generative model — can
inpaint or manually erase each tile. The watermark cost-of-removal is
"deliberate, observable image editing", not "impossible".

Treat the watermark as:

- A deterrent against casual leaks (drag-and-drop a screenshot into chat).
- A forensic trail if a leaked image surfaces with the watermark intact.

Do not treat it as a hard control.

### 6. OS-level exfiltration by a user with admin on their workstation

A user who has administrator on the box can install a clipboard logger,
intercept the rendered WebP from browser memory, or run a kernel-level
keystroke recorder. We have no agent on the endpoint and could not stop this
even in principle.

Mitigations: enforce least-privilege on workstations via MDM; do not grant
users administrator on machines that access KYC/AML data.

### 7. Real-time DoS beyond rate limits and size caps

We enforce per-request size caps (`MAX_SOURCE_BYTES`), per-render timeouts,
page count caps (`MAX_PAGES`), and page width caps (`MAX_PAGE_WIDTH`). The
Helm chart supports HPA on the worker for elastic capacity. These protect
against a single bad actor or a bad document.

We do **not** protect against:

- A botnet replaying tokens that have not yet expired (each is single-use,
  but volume across many tokens can still saturate the worker pool).
- A flood of valid tokens issued by a compromised back-office.
- Volumetric L3/L4 DoS at the network layer.

Mitigations: ingress-level rate limiting, a WAF, capacity planning for the
worker pool, and ensuring the back-office's token issuance is itself rate-
limited and observable.

### 8. Cluster-operator compromise

Anyone with `exec` on a `viewer-worker` pod, or the ability to mutate the
deployment, is inside the trust boundary. They can read S3 credentials from
mounted secrets, exfiltrate rendered pages from Redis, modify the renderer
to bypass the watermark, or shut the service down.

The cluster boundary is the boundary. Mitigations: cluster RBAC,
namespace-scoped permissions, audit logs on the Kubernetes API server,
separation of duties between the team that operates the back-office and the
team that operates the viewer cluster, and admission control that prevents
unsigned images from running.

### 9. Side-channel inference

Render time correlates with page complexity. An attacker who can issue many
valid tokens and observe response timings could in principle infer
properties of source documents they are not directly viewing (page count,
relative size, whether a render hit cache). We do not pad timings.

This is a low-impact channel for KYC/AML — the attacker would need to be
*authorised* to even ask the question — but it exists.

### 10. Compromise of the back-office signing key

If an attacker obtains the JWT signing key (or, for RS256, the private key),
they can mint tokens for any user, any object, any case. The viewer trusts
the signature. There is no second factor or revocation list inside the
viewer — by design, because tokens are short-lived (5–15 min) and the
back-office is meant to be the authority.

Mitigations: keep the signing key in an HSM or secret manager with audit;
rotate on schedule (see [`hardening.md`](hardening.md#identity-and-tokens));
monitor token issuance in the back-office; revoke compromised keys promptly
and let the short TTL bound the blast radius.

## Things we explicitly do not promise

Operators sometimes assume features that we do not have. None of the
following are implemented:

- **No download endpoint.** The API never serves original bytes. This is
  documented as a feature, but if you were expecting a "download original"
  button you will not find one.
- **No print prevention.** The browser's native print dialog is unaffected;
  the printed output carries the watermark, which is the only protection.
- **No client-side decryption.** Pages arrive as plain WebP over TLS. The
  browser holds the cleartext.
- **No per-tile dynamic watermark.** The watermark is computed once per
  render and baked into the WebP. It does not change as the user scrolls.
- **No streaming source ingestion in real time.** Sources must be readable
  by the configured backend before a token is issued.
- **No browser fingerprint check.** Anyone with a valid, unused JWT can
  fetch the page from any browser on any device.

## When to revisit this document

Re-read this list when:

- A stakeholder asks "does the viewer protect against X?"
- A new compliance requirement lands that mentions exfiltration, DLP, or
  watermarking.
- A parser CVE in pikepdf, pypdfium2, LibreOffice, Pillow, or libmagic is
  publicly disclosed.
- The architecture changes in a way that adds or removes a trust boundary.

When in doubt: this document, then [`threat-model.md`](threat-model.md), then
the design spec. Be honest with stakeholders about the trade-offs.
