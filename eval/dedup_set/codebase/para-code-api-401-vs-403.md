---
uuid: para-code-api-401-vs-403
title: API - distinguishing 401 from 403 responses
summary: Return 401 when auth is missing or bad, 403 when the caller is authenticated but not allowed - we never use 404 for forbidden items so attackers can't probe for existence.
---
## Answer
Two status codes get confused constantly:

- A **401** means the request carries no credentials, or the credentials it carries don't check out.
- A **403** means the credentials are fine, but this particular caller isn't allowed to touch the resource in question.

We deliberately avoid answering with 404 in the 403 case. Returning "not found" for something that exists but is off-limits would let an outside caller enumerate which resources exist just by watching which ones 404 versus which ones don't. So a forbidden resource always comes back as 403, keeping resource enumeration harder for anyone poking around without permission.
