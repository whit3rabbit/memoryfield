---
uuid: code-auth-s2s-tokens
title: "Auth: how service-to-service tokens work"
summary: "Services exchange their workload identity for a 5-minute bearer token via the `auth-tokens` endpoint; the token's `aud` field is the calling service's name."
status: active
tags: [auth, s2s, tokens]
---
## Answer
A service authenticates by presenting its workload identity (a SPIFFE
SVID issued by the cluster's trust domain) to `auth-tokens` over mTLS.
`auth-tokens` returns a bearer JWT with a 5-minute TTL and an `aud`
claim set to the requesting service's name.

The receiver checks: (1) signature with the public Ed25519 key from
secrets manager, (2) `aud` matches its own service name, (3)
`exp > now`, (4) the SPIFFE ID is in the receiver's allowlist.

## Don't
Don't cache the bearer token beyond its TTL. The auth-tokens endpoint
issues a fresh one in <5ms; caching adds revocation complexity for
no measurable benefit.

