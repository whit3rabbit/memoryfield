---
uuid: code-billing-idempotency
title: "Billing: idempotency key for invoice creation"
summary: "`Idempotency-Key` header on POST /invoices; replays with the same key return the original invoice without re-charging."
status: active
tags: [billing, idempotency]
---
## Answer
`POST /invoices` accepts an `Idempotency-Key` header. We store the
key + invoice UUID in Redis for 24 hours. A replay with the same
key returns the original invoice (200 OK) instead of creating a
duplicate.

Keys are scoped to the customer ID; two customers can use the same
key without conflict.

