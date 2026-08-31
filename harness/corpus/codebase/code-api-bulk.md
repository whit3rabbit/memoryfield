---
uuid: code-api-bulk
title: API: bulk endpoints and their request shapes
summary: `POST /users/bulk` accepts an array of ≤500 create requests in one call; each item gets its own status in the response array.
status: active
tags: [api, bulk]
---
## Answer
`POST /users/bulk` accepts up to 500 user-create requests in a
single call. The response is an array of per-item statuses
(success or error), not a single success/fail response.

## Don't
Don't use `POST /users` in a loop. The bulk endpoint is 10x
faster and doesn't blow your rate limit.

