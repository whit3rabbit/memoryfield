---
uuid: code-obs-request-id
title: Observability: how request IDs work
summary: Generated at the edge (UUIDv7), propagated via `X-Request-Id` header, included in every log line and trace span for that request.
status: active
tags: [observability, correlation]
---
## Answer
Edge generates a UUIDv7 per request, sets `X-Request-Id`
response header, and propagates it through every internal call.
Every log line and trace span for that request includes
`request_id`.

