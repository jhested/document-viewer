# JWT format and key management

Every `/render` and `/embed` request authenticates with a short-lived JWT that
the caller's backend issues. The viewer never issues tokens itself; it only
verifies them. The verifier lives in
`src/document_viewer/shared/jwt_auth.py`.

## Claims

All seven claims are **required**. A token missing any of them is rejected with
`401 token invalid`.

| Claim | Type | Meaning |
|---|---|---|
| `iss` | string | Issuer. If `JWT_REQUIRED_ISS` is configured, the token's `iss` must match exactly. |
| `sub` | string | The end user who will see the document. Used to build the per-user watermark and partition the cache. |
| `obj` | string | The object key the source backend should fetch (e.g. an S3 key or a filesystem path relative to `FS_ROOT`). |
| `case` | string | The KYC/AML case identifier. Surfaces in the watermark alongside `sub`. |
| `jti` | string | A unique token identifier. The viewer enforces single use via Redis `SETNX`. |
| `iat` | integer | Issued-at, seconds since epoch. |
| `exp` | integer | Expiry, seconds since epoch. Should be minutes-to-an-hour ahead — see "Lifetime guidance". |

The watermark text is built from `sub` and `case`
(`"{sub} - {case}"`), so any value safe to render as a visible watermark is
fine; emails, internal user IDs, and case numbers all work.

## Algorithms

The viewer accepts exactly one algorithm per deployment, controlled by
`JWT_ALGORITHM`:

- **`RS256`** — recommended. The viewer holds the public key; the issuer
  holds the private key. Compromise of the viewer image cannot mint tokens.
  Configure with `JWT_PUBLIC_KEY` (PEM, multi-line via `\n` is fine for
  env-based config).
- **`HS256`** — simpler. Issuer and verifier share a secret. Acceptable when
  both run inside the same trust boundary. Configure with `JWT_HMAC_SECRET`.

## Replay protection

Each successful verification calls `JwtReplayGuard.claim(claims)`, which runs
`SETNX` on `jti:{jti}` in Redis with a TTL equal to the token's remaining
lifetime (`exp - now`, minimum 1 second). The first request wins. Every
subsequent use of the same `jti` returns `401 token replayed`.

This means a token is **single-use** by default. If you need to fetch the
manifest and then several pages, mint one token per request, or front the
viewer with a short-lived session token your backend issues.

## Generating RS256 keys

```bash
openssl genpkey -algorithm RSA -out private.pem -pkeyopt rsa_keygen_bits:2048
openssl pkey -in private.pem -pubout -out public.pem
```

Distribute:

- `private.pem` — only to the service that signs tokens. Treat as a production
  secret.
- `public.pem` — to the viewer, via `JWT_PUBLIC_KEY`.

To rotate:

1. Generate the new keypair.
2. Deploy the new `public.pem` to the viewer alongside the existing one — for
   RS256, a deployment can list multiple acceptable public keys behind a
   reverse proxy or via a JWKS endpoint pattern if you wrap the verifier;
   the bundled verifier accepts one key at a time, so coordinate via a
   short cutover window during which both signing services are still
   accepting the old key.
3. Switch the signing service to use the new private key.
4. After the old token's max lifetime has elapsed, remove the old public key.
5. Continue allowing the replay cache to drain (see below).

## HS256 secret rotation

If you operate HS256, the secret is shared between issuer and verifier. Use a
secret of **at least 32 bytes** of cryptographically random data. A simple way
to generate one:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Example placeholder (do **not** use this in production):

```
JWT_HMAC_SECRET=your-32-byte-or-longer-jwt-secret-here
```

Rotation is a **swap-then-purge** pattern:

1. **Pick the new secret.** 32+ bytes of randomness.
2. **Swap.** Update the verifier deployment to the new secret. Tokens signed
   under the old secret will immediately start failing with `401 token
   invalid`. Update the issuer deployment to the new secret in the same
   change window. (If you cannot swap atomically, accept a short outage on
   in-flight tokens — they are short-lived by design.)
3. **Purge the replay cache.** Old `jti:*` entries in Redis are still valid as
   replay records, but their associated tokens can no longer verify. Wait one
   full token lifetime (`exp - iat` of the longest token you issue) before
   declaring rotation complete; after that window, no token signed under the
   old secret can verify, regardless of whether its `jti` is still in Redis.
4. **Confirm.** Run a smoke test with a freshly minted token, and verify a
   token signed under the old secret returns `401`.

## Lifetime guidance

- **Aim short.** Minutes, not hours. Five to fifteen minutes covers most
  KYC/AML reviewer workflows.
- **One token per request is fine.** Replay protection makes long-lived tokens
  unnecessary.
- **`iat` skew tolerance is small.** Keep your issuer's clock in sync via NTP.

## Worked example payload

```json
{
  "iss": "kyc-reviewer-api",
  "sub": "agent-42@example.com",
  "obj": "cases/2026/05/case-9912/passport.pdf",
  "case": "CASE-9912",
  "jti": "01HZ8T4X5N7Y9JE9P3K0WQABCD",
  "iat": 1747840000,
  "exp": 1747840600
}
```

For working signing code in Python (`PyJWT`) and Node.js (`jsonwebtoken`), see
`docs/integration/issuing-tokens.md`.
