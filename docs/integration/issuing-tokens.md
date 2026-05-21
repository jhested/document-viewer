# Issuing tokens

The document-viewer never issues tokens; your backend does. This page shows
how to sign a viewer-compatible JWT in Python and Node.js using the libraries
the viewer itself uses or interoperates with: `PyJWT` and `jsonwebtoken`.

For the full claim format, algorithm choice, and rotation guidance, see
`docs/api/jwt.md`.

## Required claims (recap)

`iss`, `sub`, `obj`, `case`, `jti`, `iat`, `exp` — all required.

## Python — `PyJWT` (HS256)

```bash
pip install PyJWT
```

```python
"""Issue a viewer JWT (HS256)."""
from __future__ import annotations

import time
import uuid

import jwt  # PyJWT

# Use a real 32+ byte secret in production. Load from a secret manager.
SECRET = "your-32-byte-or-longer-jwt-secret-here"


def issue_viewer_token(
    *,
    issuer: str,
    user: str,
    object_key: str,
    case_id: str,
    ttl_seconds: int = 300,
) -> str:
    now = int(time.time())
    claims = {
        "iss": issuer,
        "sub": user,
        "obj": object_key,
        "case": case_id,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")


if __name__ == "__main__":
    token = issue_viewer_token(
        issuer="kyc-reviewer-api",
        user="agent-42@example.com",
        object_key="cases/2026/05/case-9912/passport.pdf",
        case_id="CASE-9912",
    )
    print(token)
```

## Python — `PyJWT` (RS256)

```python
"""Issue a viewer JWT (RS256)."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import jwt  # PyJWT

PRIVATE_KEY = Path("/etc/issuer/keys/private.pem").read_text()


def issue_viewer_token(
    *,
    issuer: str,
    user: str,
    object_key: str,
    case_id: str,
    ttl_seconds: int = 300,
) -> str:
    now = int(time.time())
    claims = {
        "iss": issuer,
        "sub": user,
        "obj": object_key,
        "case": case_id,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256")
```

Generate the keypair with:

```bash
openssl genpkey -algorithm RSA -out private.pem -pkeyopt rsa_keygen_bits:2048
openssl pkey -in private.pem -pubout -out public.pem
```

## Node.js — `jsonwebtoken` (HS256)

```bash
npm install jsonwebtoken
```

```javascript
// Issue a viewer JWT (HS256).
import jwt from "jsonwebtoken";
import { randomUUID } from "node:crypto";

// Use a real 32+ byte secret in production. Load from a secret manager.
const SECRET = "your-32-byte-or-longer-jwt-secret-here";

export function issueViewerToken({
  issuer,
  user,
  objectKey,
  caseId,
  ttlSeconds = 300,
}) {
  const now = Math.floor(Date.now() / 1000);
  const claims = {
    iss: issuer,
    sub: user,
    obj: objectKey,
    case: caseId,
    jti: randomUUID().replace(/-/g, ""),
    iat: now,
    exp: now + ttlSeconds,
  };
  return jwt.sign(claims, SECRET, { algorithm: "HS256" });
}

const token = issueViewerToken({
  issuer: "kyc-reviewer-api",
  user: "agent-42@example.com",
  objectKey: "cases/2026/05/case-9912/passport.pdf",
  caseId: "CASE-9912",
});
console.log(token);
```

## Node.js — `jsonwebtoken` (RS256)

```javascript
// Issue a viewer JWT (RS256).
import jwt from "jsonwebtoken";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

const PRIVATE_KEY = readFileSync("/etc/issuer/keys/private.pem", "utf8");

export function issueViewerToken({
  issuer,
  user,
  objectKey,
  caseId,
  ttlSeconds = 300,
}) {
  const now = Math.floor(Date.now() / 1000);
  const claims = {
    iss: issuer,
    sub: user,
    obj: objectKey,
    case: caseId,
    jti: randomUUID().replace(/-/g, ""),
    iat: now,
    exp: now + ttlSeconds,
  };
  return jwt.sign(claims, PRIVATE_KEY, { algorithm: "RS256" });
}
```

## Notes

- **One token per request.** Replay protection consumes the `jti` on first
  use. If your UI fetches the manifest and then several pages, mint one token
  per fetch.
- **Don't reuse `jti`.** Generate it fresh per token. `uuid.uuid4()` /
  `randomUUID()` is fine; ULIDs are fine too.
- **Keep `ttl_seconds` small.** Five to fifteen minutes is typical. Long
  lifetimes increase the window during which a leaked token is dangerous.
- **The viewer is not your auth layer.** Token issuance is a chance to enforce
  reviewer-side checks: is this reviewer authorized to see this case? Is the
  object actually associated with the case? Apply those checks before signing.
