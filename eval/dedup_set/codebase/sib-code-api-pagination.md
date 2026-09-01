---
uuid: sib-code-api-pagination
title: API - rate limit headers returned on GET /users
summary: Every response on GET /users carries rate-limit headers, and the endpoint caps callers at 300 requests per 5-minute window per API key.
---
## Answer
`GET /users` (and most read endpoints) enforce a sliding-window limit of 300 requests per 5 minutes, keyed by API key rather than IP. Every response, successful or not, includes:

- `X-RateLimit-Remaining`: requests left in the current window
- `X-RateLimit-Reset`: unix timestamp when the window resets

Exceeding the limit returns `429 Too Many Requests` with a `Retry-After` header in seconds. Clients should back off using that header value rather than a fixed retry interval, since the window is sliding and a fixed delay can still land mid-limit.

Internal service-to-service calls (identified by the `svc_` API key prefix) get a higher limit of 3000/5min, configured in `ratelimit.yaml`.
