---
uuid: code-api-problem-details
title: "API: why errors return RFC 7807 problem details"
summary: "Errors are JSON `application/problem+json` with `type`, `title`, `status`, `detail`, `instance`; clients can render `title` and `detail` directly."
status: active
tags: [api, errors]
---
## Answer
Error responses are `application/problem+json`:
```json
{
  "type": "https://ledger.example.com/errors/insufficient-funds",
  "title": "Insufficient funds",
  "status": 402,
  "detail": "Account has $12.50; transfer requires $50.00",
  "instance": "/v1/transfers"
}
```
The `type` URL is human-readable documentation.

