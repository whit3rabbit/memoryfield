---
uuid: code-auth-rotate-jwt-key
title: Auth: rotating the JWT signing key
summary: Run `make rotate-jwt-key`; redeploys auth service in 60s; old keys valid for 5-minute overlap window.
status: active
tags: [auth, jwt, rotation, ops]
source: ops/runbook/auth.md#rotate-jwt
---
## Answer
Run `make rotate-jwt-key`. That target generates a new Ed25519 keypair,
uploads the public half to the secrets manager, and triggers a rolling
restart of the auth service. Old keys remain valid for 300 seconds
(configured via `JWT_OVERLAP_WINDOW`) so in-flight tokens still verify.

## Why the overlap
Rotating without an overlap breaks every long-poll connection for ~30s
of clock skew. 5 minutes is overkill for our traffic but cheap.

## Don't
- Don't rotate the key by hand-editing the secrets manager. The
  makefile target also bumps the key version label that auth clients
  cache; without it, every API client re-validates against an unknown
  key id for an hour.
- Don't rotate during the deploy window 09:00–10:00 UTC. The deploy
  itself triggers auth-service restarts and a key rotation on top
  looks identical in the logs.

