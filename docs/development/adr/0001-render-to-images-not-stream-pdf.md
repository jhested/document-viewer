# Render to images, not stream PDFs

- Status: Accepted
- Date: 2026-05-20

## Context and Problem Statement

The viewer must show KYC/AML source documents (PDF, office formats, images, HEIC) to back-office reviewers without letting those reviewers save or exfiltrate the original file. The original bytes are PII and frequently include scans of passports, ID cards, and proof-of-address documents. We also need a uniform rendering path so the security posture does not vary by source type, and we need to guarantee that every page a reviewer sees carries a baked-in watermark.

## Decision Drivers

- The original source bytes must never reach the browser.
- Watermarking must be tamper-evident — i.e. baked into the pixels, not overlaid in the DOM.
- A single rendering pipeline simplifies the security review for all source formats.
- We want to keep parsing of untrusted bytes server-side, inside a sandboxed worker.

## Considered Options

- Render every page to a per-page WebP on the server; serve only images.
- Stream the original PDF to a client-side PDF.js viewer.
- Embed Microsoft Office Online / a SaaS viewer for office files.
- Build a bespoke iframe sandbox that renders the PDF in-browser with a CSP lockdown.

## Decision Outcome

Chosen option: "Render every page to a per-page WebP on the server", because it is the only option where the original bytes never leave the worker container. PDF.js and any in-browser viewer must hold the source bytes to render them; SaaS viewers send PII to a third party; iframe sandboxes are bypassable from devtools.

### Consequences

- Good, because the original file is structurally inaccessible to the browser — no "save as", no view-source escape.
- Good, because watermarks are composited into the WebP pixels (Pillow `ImageDraw`) and survive screenshots as evidence.
- Bad, because rendering costs server CPU; the worker pool must be sized for it.
- Bad, because reviewers lose native PDF text selection, search, and accessibility features.
- Neutral: caching of per-page WebPs in Redis keeps repeat views cheap.
