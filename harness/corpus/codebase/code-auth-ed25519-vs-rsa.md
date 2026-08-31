---
uuid: code-auth-ed25519-vs-rsa
title: Auth: why we use Ed25519 not RSA
summary: Ed25519 is 10x faster to verify; tokens are short; we never need to encrypt them.
status: active
tags: [auth, jwt, design]
---
## Answer
We sign JWTs with Ed25519 because (a) verification is roughly 10x
faster than RSA-2048, which matters at peak (~8k token checks/sec),
and (b) the token header stays short enough to fit in a single TCP
packet with our edge proxy's header limits.

We don't need RSA's encrypt-decrypt capability — JWTs are signed, not
encrypted. The payload is base64 but readable.

## Don't
Don't propose switching to P-256 ECDSA "for compatibility". The
legacy clients that needed P-256 were deprecated in 2024; current
clients are all Ed25519-capable.

