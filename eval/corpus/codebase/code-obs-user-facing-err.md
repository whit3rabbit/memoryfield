---
uuid: code-obs-user-facing-err
title: "Observability: what counts as a user-facing error"
summary: "Any 5xx response to a request that originated from a user (not a service-to-service call) and was not a 4xx due to bad client input."
status: active
tags: [observability, metrics]
---
## Answer
For SLO purposes:
- User-facing 5xx → counts as error.
- 4xx (except 429 rate-limit) → counts as error (caller did
  something wrong).
- Service-to-service 5xx → counts only on the originating service.

