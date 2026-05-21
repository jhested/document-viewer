# React + C# document-viewer sample

A complete end-to-end demo:

- **React 19 + Vite + TypeScript** frontend — upload files, list them, click to preview.
- **ASP.NET Core 9 (C#)** backend — issues presigned S3 PUT URLs and mints viewer JWTs.
- **MinIO** S3-compatible storage.
- **document-viewer** (this repo's `viewer-api` + `viewer-worker`) for rendering.

## Architecture

```
┌────────────────┐          ┌────────────────┐          ┌────────────┐
│ React frontend │──upload─►│ MinIO (S3)     │◄──read───│ viewer-    │
│ :5173          │          │ :9000          │          │ worker     │
│                │          └────────────────┘          └────────────┘
│                │                                            ▲
│                │──presign URL──┐                            │
│                │──viewer-token─┤                            │
│                │               ▼                            │
│                │       ┌────────────────┐          ┌────────┴───┐
│                │──────►│ Backend (.NET) │          │ viewer-api │
│                │       │ :5099          │          │ :8000      │
│                │       └────────────────┘          └────────────┘
│                │                                            ▲
│  <iframe       │────────────────────────────────────────────┘
│   src="…/embed/{token}">                                    
└────────────────┘
```

The frontend never sees the file bytes after upload, and never sees S3
credentials. It asks the backend for a presigned PUT URL, uploads directly to
MinIO, asks the backend for a short-lived viewer JWT scoped to one object, and
embeds the document-viewer's `/embed/{jwt}` page in an iframe.

## Running

> **Heads up:** ports 8000, 9000, 9001, 3000, and 5099 are used. If the
> integration-test stack (`compose.test.yaml` at the repo root) is up, take it
> down first: `docker compose -f ../../compose.test.yaml down`.

### 1. Bring up the backend stack

From this directory:

```bash
docker compose up -d --wait
```

That builds and starts MinIO, Redis, Gotenberg, viewer-api, viewer-worker, and
the C# backend. First run pulls a lot of images and builds three Dockerfiles —
budget ~10 min.

### 2. Run the React dev server

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>, enter a username, drop a PDF or .docx onto the
upload box, click the entry to preview.

## What to look at

- **`backend/Program.cs`** — A minimal ASP.NET Core API with three endpoints:
  - `POST /api/uploads` returns a presigned PUT URL with the right `Content-Type`.
  - `GET /api/documents?user=…` lists the user's S3 objects.
  - `POST /api/viewer-token` mints an HS256 JWT (`iss`, `sub`, `obj`, `case`, `jti`, `iat`, `exp`) and returns `{ token, embedUrl }`.
- **`frontend/src/api.ts`** — Typed wrapper around those three endpoints, plus
  the direct browser-to-MinIO PUT.
- **`frontend/src/App.tsx`** — The whole UI: login, upload, list, embed.

## Production notes (i.e. don't copy this as-is)

- The HMAC secret in `compose.yaml` is the integration-test secret. Replace it
  with a real 32+ byte secret from a secrets manager.
- The backend trusts the `user` field from the frontend. In production, identity
  should come from your auth layer (an OIDC session, SAML, etc.), not the client
  request body.
- S3 credentials in `compose.yaml` are read/write. The viewer-worker only needs
  `s3:GetObject`; the backend needs `s3:PutObject` + `s3:ListBucket`. Split
  them, scope them by prefix.
- CORS on MinIO is wide-open in dev. In production, restrict it to your
  frontend origin.
- The presigned PUT URL expires in 10 minutes. Tune for your UX.
- Viewer JWTs have a 5-minute TTL. The viewer's replay guard claims `jti` on
  `/manifest`; if your UI reloads the iframe, mint a fresh token.
