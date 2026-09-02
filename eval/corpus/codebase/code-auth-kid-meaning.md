---
uuid: code-auth-kid-meaning
title: "Auth: what the token `kid` header means"
summary: "`kid` is the key version label; verifiers must check it against the active key set, not the signing key's URL."
status: active
tags: [auth, jwt, kid]
---
## Answer
`kid` (key ID) is a version label that identifies which key from
the secrets manager signed this token. Format: `v<n>-<sha256[:8]>`
(e.g., `v42-7a3b9c1e`).

Verifiers must look up the key by `kid`, not by a fixed URL — when
the key rotates, the URL stays the same but the `kid` changes.

## Don't
Don't trust a token whose `kid` is not in your active key set,
even if the signature math checks out. Old-key tokens should have
expired by now.

