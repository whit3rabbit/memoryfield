---
uuid: code-auth-public-keys
title: "Auth: where the public keys live"
summary: "Active keys are in `secrets://auth/jwt/active`; rotated-out keys live in `secrets://auth/jwt/history/<version>` for 30 days."
status: active
tags: [auth, jwt, secrets]
---
## Answer
Public keys are published to the secrets manager at
`auth/jwt/active` (the current signing key) and
`auth/jwt/history/<version>` (rotated-out keys, retained for 30
days so overlap-window tokens still verify).

Every service subscribes to changes via the secrets manager's
watch API and caches the active key in memory.

## Don't
Don't fetch the key on every JWT verification. The watch subscription
updates the in-memory cache within 100ms of rotation; re-fetching
adds 5–10ms per verify and trashes the secrets manager's quota.

