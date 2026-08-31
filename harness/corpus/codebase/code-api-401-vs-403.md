---
uuid: code-api-401-vs-403
title: API: the difference between 401 and 403
summary: 401 = no/invalid auth; 403 = auth valid but caller lacks permission. We always return 403 (never 404) for forbidden resources to avoid resource enumeration.
status: active
tags: [api, auth, status-codes]
---
## Answer
- **401 Unauthorized**: missing or invalid auth.
- **403 Forbidden**: auth valid but the caller can't access
  this resource.

We always return 403 for forbidden resources (never 404) to
make resource enumeration harder.

