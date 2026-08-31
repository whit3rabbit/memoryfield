---
uuid: code-api-graceful-shutdown
title: API: graceful shutdown behavior
summary: On SIGTERM, server stops accepting new requests, drains in-flight ones up to 30s, then exits non-zero if any are still running.
status: active
tags: [api, lifecycle]
---
## Answer
On SIGTERM:
1. Stop accepting new connections.
2. Wait for in-flight requests up to 30s.
3. Force-exit with code 1 if any are still running.

## Don't
Don't set the graceful-shutdown timeout above 30s — it makes
pod replacement visibly slow during deploys.

