# Gotenberg vs bespoke LibreOffice container

- Status: Accepted
- Date: 2026-05-20

## Context and Problem Statement

The viewer must accept office formats (`.docx`, `.pptx`, `.xlsx`, `.odt`, `.ods`, `.odp`, `.rtf`) and convert them to PDF before the rest of the pipeline (pikepdf clean, pypdfium2 render). The only realistic open-source converter for these formats is LibreOffice, which is a large desktop application with a wide attack surface. We need that conversion in production but want to minimise what runs inside our own worker image, and we want strict network isolation around the converter.

## Decision Drivers

- Keep the worker image small and its attack surface narrow.
- Isolate the LibreOffice process in its own container with its own NetworkPolicy.
- Prefer a maintained upstream over rolling our own headless-LibreOffice wrapper.
- Never ship source bytes to a third party.

## Considered Options

- Run [Gotenberg](https://gotenberg.dev/) as a sidecar HTTP service (`gotenberg/gotenberg:8`, pinned by digest) and call its `/forms/libreoffice/convert` endpoint.
- Bake LibreOffice directly into the `viewer-worker` image and drive it via UNO or `soffice --headless`.
- Use a third-party SaaS converter (CloudConvert, Aspose, etc.).

## Decision Outcome

Chosen option: "Gotenberg as a sidecar HTTP service", because it gives us a maintained, hardened upstream and a clean security boundary. The worker talks to Gotenberg only over an internal HTTP network; Gotenberg has its own egress-default-deny NetworkPolicy in the Helm chart.

### Consequences

- Good, because LibreOffice's process capabilities live in a separate container, not in our parser worker.
- Good, because Gotenberg internally recycles LibreOffice processes per request, so per-job state is bounded.
- Bad, because we operate one more container and must keep its image digest pinned and updated.
- Bad, because debugging a failed conversion now requires reading Gotenberg logs, not a local stack trace.
- Neutral: cold start of the office path depends on Gotenberg readiness, but the container stays running between jobs.
