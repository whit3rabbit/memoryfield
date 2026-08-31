---
uuid: code-api-versioning
title: API: how versioning works
summary: URL path version (`/v1/`, `/v2/`); the `Accept` header is *not* used for version negotiation.
status: active
tags: [api, versioning]
---
## Answer
Version is in the URL path: `/v1/users`, `/v2/users`. We do not
honor `Accept: application/vnd.ledger.v2+json` style version
headers.

## Don't
Don't add an `API-Version` header — clients keep forgetting it,
and we keep forgetting to validate it.

