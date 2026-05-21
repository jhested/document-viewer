# Coordinated vulnerability disclosure

This document expands on the top-level [`SECURITY.md`](../../SECURITY.md). If
you have found a security issue, follow the reporting instructions in
`SECURITY.md` first — that is the authoritative contact.

## Scope

In scope:

- Code in this repository.
- Container images we publish (`document-viewer-api`, `document-viewer-worker`).
- The Helm chart shipped from this repository.

Out of scope:

- Vulnerabilities in upstream dependencies (Gotenberg, LibreOffice, PDFium,
  Pillow, libmagic, pikepdf, FastAPI). Please report those to the upstream
  project. We will pick up fixes once they ship and re-pin promptly.
- Deployments operated by third parties (e.g. a bank running their own
  document-viewer install). Contact the operator of that deployment.
- Social-engineering or phishing of project maintainers.
- Issues that require an attacker to already be inside the cluster trust
  boundary (e.g. with `exec` permissions on a viewer pod) — see
  [`threat-model.md`](threat-model.md) for the documented trust boundaries.

## Reporting channel

Use the contact listed in [`SECURITY.md`](../../SECURITY.md). Do **not** open a
public GitHub issue, pull request, or discussion for a suspected
vulnerability. Do **not** announce the issue on social media or third-party
forums before disclosure.

When reporting, include:

1. A description of the issue and its impact.
2. Reproduction steps or a proof-of-concept (a minimal corpus file is ideal
   for parser bugs).
3. The affected version(s), if known.
4. Your preferred credit name (or a request for anonymity).
5. Whether you intend to publish your own write-up, and on what timeline.

## Disclosure timeline

This restates the timeline in [`SECURITY.md`](../../SECURITY.md) for visibility
and adds operational detail.

| Day | Event |
|---|---|
| T+0 | Report received. Auto-reply confirms receipt. |
| T+3 (business days) | Maintainer acknowledgement: a human has read the report. |
| T+14 | Initial assessment shared with the reporter: severity estimate, whether it is in scope, expected remediation track. |
| T+30 | Fix in progress or, if the issue is invalid/won't-fix, a final response with rationale. |
| T+90 | Default coordinated public disclosure. Earlier if a fix has shipped and been verified; later only by mutual agreement (see "Embargo extensions" below). |

If we go silent at any milestone, escalate by replying to the original thread
with the subject prefixed `[REMINDER]`. If we are still silent 7 days after a
reminder, you are released from the embargo and may disclose.

## Embargo

Default embargo length is **90 days from maintainer acknowledgement** (T+3),
not from the original report date.

### Embargo extensions

We may request an extension if:

- The fix requires coordinated release with an upstream project (e.g.
  pikepdf, pypdfium2) and they need more time.
- The fix is complex and a rushed patch would cause regressions.
- A coordinated multi-party announcement is appropriate.

Extensions are by **mutual agreement** with the reporter. We will not extend
unilaterally. If the reporter declines, the original 90-day deadline holds.

### Embargo break

We will release earlier than T+90 if:

- The vulnerability is being actively exploited in the wild.
- The vulnerability has been independently disclosed by another party.
- The maintainer judges that user safety is better served by disclosure than
  by waiting.

In any of these cases the reporter will be notified before public disclosure
wherever practical.

## CVE filing

We use [MITRE](https://cve.mitre.org/) as our CVE Numbering Authority of last
resort. For each in-scope vulnerability we judge to be a CVE-worthy issue
(roughly: anything an operator running the project would want to know about
from a CVE feed):

- We request a CVE via MITRE's web form during the assessment phase (T+14).
- The CVE number is shared with the reporter once issued.
- The CVE is published when the embargo lifts, with details matching the
  public advisory.
- If GitHub Security Advisories assigns a CVE through their integration, we
  use that instead — but the disclosure timeline above still governs
  publication.

We will not file a CVE for:

- Operator misconfigurations (covered in [`hardening.md`](hardening.md)).
- Upstream dependency bugs (reported to the upstream).
- Defense-in-depth improvements that are not exploitable on their own.

## Credit and anonymity

Reporters are credited by default in the advisory and changelog. You may
request:

- **Public credit** with a name, handle, and/or organisation.
- **Public credit** with a name only.
- **Anonymous credit** (the advisory will say "an external researcher").
- **No mention at all** (the advisory will describe the fix without
  identifying the source).

State your preference in the original report. If you do not state one we will
ask before publishing.

We do not offer monetary bounties for this project. If your organisation
forbids accepting credit on third-party advisories, we will respect that.

## What you can expect from us

- A human will reply to your report inside 3 business days.
- We will not threaten legal action against good-faith research conducted
  inside the scope above.
- We will not name you publicly without your explicit consent.
- We will share the draft advisory with you before publication, so you can
  verify the technical content and your credit line.
- We will not silently fix the bug and ship a release without telling you;
  if we shipped the fix, we tell you, and we publish on the agreed date.

## What we ask from you

- Do not access, modify, or exfiltrate data you do not own while researching.
- Do not run denial-of-service tests against deployments you do not operate.
- Give us a reasonable time to fix the issue before going public.
- Stop and ask if you are unsure whether something is in scope.
