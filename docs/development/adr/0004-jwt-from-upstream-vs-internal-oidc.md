# JWT from upstream vs internal OIDC

- Status: Accepted
- Date: 2026-05-20

## Context and Problem Statement

The viewer must restrict access to each rendered document to the specific reviewer working a specific case. The upstream back-office (the KYC console) already authenticates reviewers, knows the case context, and decides which document a reviewer should see. The viewer must enforce that decision but should not duplicate authentication state or hold long-lived user sessions of its own. Tokens must be short-lived, single-use, and revocable per document.

## Decision Drivers

- The viewer must not hold long-lived user sessions or duplicate AuthN state.
- Access decisions belong to the back-office, which already knows the user and the case.
- Tokens must be scoped to a single document and revocable per-document.
- The viewer must remain stateless apart from its render cache.

## Considered Options

- Upstream mints a short-lived JWT scoped to one document; the viewer verifies and enforces single-use via Redis SETNX on the `jti`.
- Viewer holds its own OIDC session against the back-office IdP.
- Shared-cookie SSO between back-office and viewer hostnames.
- Pre-signed S3 URLs handed to the browser, with no viewer-level auth.

## Decision Outcome

Chosen option: "Upstream-minted JWT, viewer verifies and replay-protects", because access is already a back-office decision and a short-lived signed token is the minimum mechanism that conveys it without giving the viewer its own session store.

### Consequences

- Good, because the viewer needs only a verify key and Redis; no session store, no IdP integration.
- Good, because revocation is per-document: don't issue the token, or block the `jti` in Redis.
- Good, because tokens fit in a URL path and can be embedded as `<img src>`.
- Bad, because the back-office is now responsible for correct claims (`sub`, `doc`, `iss`, `exp`, `jti`); a bug there is an access bug.
- Neutral: replay protection uses Redis `SETNX` with TTL = `exp - now`, so expired entries self-evict.
