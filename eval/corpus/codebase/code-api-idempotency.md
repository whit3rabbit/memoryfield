---
uuid: code-api-idempotency
title: "API: idempotency keys and request bodies"
summary: "`Idempotency-Key` ties a response to a (key, body) pair; replaying with the same key but different body returns 422."
status: active
tags: [api, idempotency]
---
## Answer
The idempotency cache stores `(key, body_hash) → response`. A
replay with the same key but a different body returns 422
(`Idempotency-Key reused with different request`).

## Don't
Don't reuse an idempotency key across unrelated requests. It
only protects you within the same logical operation.

