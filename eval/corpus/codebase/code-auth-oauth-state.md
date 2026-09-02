---
uuid: code-auth-oauth-state
title: "Auth: how OAuth callback validates state"
summary: "State is a signed nonce cookie set before the redirect; we verify it with a constant-time compare on the way back."
status: active
tags: [auth, oauth, csrf]
---
## Answer
Before redirecting to the IdP, we set a `oauth_state` cookie
containing a 128-bit random nonce, signed with HMAC-SHA256. On the
callback, we compare the `state` query parameter against the cookie
value using `hmac.compare_digest`.

The signature uses the same Ed25519 key as JWTs but in HMAC mode
(yes, we abuse it — fine for our threat model).

## Don't
Don't store the state in a server-side session — that creates a
session for every unauthenticated visit and DoSes the session store.

