# Sample app tech stack

- Status: Accepted
- Date: 2026-05-21

## Context and Problem Statement

We need a runnable, end-to-end **sample integration** that shows a back-office
team how to wire the `document-viewer` into a real product flow: upload a file
to S3 from a browser, then preview it in the viewer. This is a teaching
artefact under `examples/`, not a production service.

Its job is to be **clear, runnable from a fresh clone in one command, and
representative** of the patterns a real back-office would use. It's not a
reference architecture and doesn't need to scale.

## Decision Drivers

- **Onboarding speed.** A reader should be able to clone, run
  `docker compose up`, run `npm run dev`, and have a working stack within a
  few minutes. Anything more is friction that competes with the value the
  sample is supposed to deliver.
- **Audience match.** Back-office teams integrating with this viewer are
  enterprise teams. The dominant backend language in that audience is C#
  (.NET) or Java; the dominant frontend is React. We're optimising for the
  team that's most likely to be the integrator, not for what's most natural
  given the viewer is Python.
- **Show the right pattern, not a clever pattern.** Presigned PUT URLs from
  the back-office to S3, then a short-lived JWT for the viewer — that's the
  intended integration pattern for the viewer itself. The sample has to
  demonstrate exactly that, not invent an alternative.
- **Self-contained.** The sample should not require running services on the
  host or accounts on third-party services to demo. Local MinIO is enough.
- **No production code masquerade.** The sample uses the integration-test
  HMAC secret and a wide-open CORS policy — `README.md` calls out everything
  that needs to change before production, so nothing here is mistaken for
  hardening guidance.

## Considered Options

### Frontend framework

- **React 19** — chosen
- Vue 3 / Svelte 5 / SolidJS
- Plain HTML + a small script tag

### Frontend build tool

- **Vite 6** — chosen
- Next.js (or Remix, TanStack Start, etc.)
- Webpack / Parcel / Rollup directly

### Frontend language

- **TypeScript** — chosen
- Plain JavaScript

### Backend language / runtime

- **ASP.NET Core 10 (C#)** — chosen
- Node.js + Express / Fastify / Hono
- Python + FastAPI (matches the viewer's own stack)
- Go + chi / net/http

### Upload mechanism

- **Browser → S3 via presigned PUT URL** — chosen
- Browser → backend → S3 (server-mediated, bytes through backend)
- Browser → backend → backend writes to a local FS share

### Viewer embed mechanism

- **`<iframe src="/embed/{jwt}">` (bundled viewer page)** — chosen
- Custom JS calling `/render/{jwt}/manifest` + `/render/{jwt}/page/N` directly
- Pre-render every page server-side

## Decision Outcome

| Axis | Choice | Why this over the alternatives |
|---|---|---|
| Frontend framework | **React 19** | The audience runs React. A sample in Svelte would teach the right pattern in the wrong dialect. React 19 in particular because StrictMode dev-time double-renders surface real bugs (and we exposed and accepted one — see `App.tsx` race-guard). |
| Build tool | **Vite 6** | Zero-config dev server, native ESM, instant startup. Next.js would tempt readers to copy SSR conventions that don't apply to a thin SPA. |
| Frontend language | **TypeScript** | The presign/upload/mint flow is easy to get wrong (header mismatches, claim names). Static types catch the wrong shape at the boundary; the cost is a one-line `tsc -b`. |
| Backend lang | **ASP.NET Core 10 (C#)** | Matches the dominant enterprise integrator language. The framework's minimal-API style (`MapPost` + record types) keeps the whole backend at ~170 lines, comparable to a Node/FastAPI version. JWT signing uses the in-box `System.IdentityModel.Tokens.Jwt`; S3 via `AWSSDK.S3`. We rejected Node because it would have been our second JS surface; we rejected Python because it would have made the sample look like an extension of the viewer's own code rather than a clear consumer of it. |
| Upload mechanism | **Browser → S3 via presigned PUT** | The intended pattern for the viewer ecosystem. Server-mediated upload would route file bytes through the back-office, which defeats the point of having S3 in the loop. The presigned-URL pattern is also what real back-offices already do for unrelated uploads. |
| Viewer embed | **`<iframe src="/embed/{jwt}">`** | The simplest path to a working preview, and the one most likely to be copy-pasted directly into a back-office's case-detail view. Pattern 3 (custom JS) is documented in `docs/integration/embedding.md` for teams that need finer control. |

### Consequences

- **Good** — A reader can copy the C# `MapPost("/api/uploads", …)` and
  `MapPost("/api/viewer-token", …)` blocks into an existing ASP.NET service
  with no friction. The exact AWS SDK calls and the exact claim set carry
  over verbatim.
- **Good** — The sample exposes real, non-obvious foot-guns of the chosen
  stack: the AWS SDK for .NET defaults presigned URLs to HTTPS regardless of
  `ServiceURL`, and sig-v4 covers the Host header so the signing client has
  to use the *browser-facing* endpoint. These are surfaced in `Program.cs`
  comments and the README's "don't copy as-is" list.
- **Bad** — The sample's stack drifts from the viewer's own (Python +
  FastAPI). A reader looking at both has to context-switch. The README's
  architecture diagram tries to make the boundary obvious.
- **Bad** — Three runtimes in the demo (.NET, Node for Vite dev server,
  Python for the viewer itself) is more than the absolute minimum. We
  accept the cost because each is the *right* runtime for its slice and
  hiding any of them would distort what the integrator actually needs.
- **Neutral** — JWT signing recipes for Python and Node already live in
  `docs/integration/issuing-tokens.md`. The C# version is in
  `examples/react-upload-preview/backend/Program.cs` rather than that
  document; if a third reader asks for it we'll promote it.
- **Neutral** — MinIO (vs LocalStack) was implicit; we already use MinIO in
  `compose.test.yaml` and reusing the same image keeps the example aligned
  with how the viewer is integration-tested.
