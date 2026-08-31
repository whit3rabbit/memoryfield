---
uuid: code-api-rate-limit
title: API: rate limiting per API key
summary: Token bucket: 1000 req/min sustained + burst of 100; `429` includes `X-RateLimit-Reset` header in seconds.
status: active
tags: [api, rate-limit]
---
## Answer
Per-API-key rate limit: 1000 req/min sustained, burst of 100.
On limit, server returns 429 with `X-RateLimit-Reset` (seconds
until reset).

## Don't
Don't hammer the API when you get a 429. The reset header tells
you when to retry.

