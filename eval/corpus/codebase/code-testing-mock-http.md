---
uuid: code-testing-mock-http
title: "Testing: how to mock external HTTP calls"
summary: "Use `responses` (requests) or `httpx_mock` (httpx); never use `unittest.mock.patch` on `requests.get` directly."
status: active
tags: [testing, mocking]
---
## Answer
For `requests`-based code, use the `responses` library. For
`httpx`, use `httpx_mock`. Both intercept at the transport
layer and don't require patching internals.

## Don't
Don't `unittest.mock.patch('requests.get')` — it bypasses
transport-level concerns (TLS, retries).

