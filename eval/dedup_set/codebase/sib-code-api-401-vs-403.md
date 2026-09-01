---
uuid: sib-code-api-401-vs-403
title: API - when we return 422 instead of 400
summary: 400 means the request body is malformed or missing required fields, 422 means it parsed fine but failed semantic validation like an invalid state transition.
---
## Answer
- **400 Bad Request**: the payload itself is broken - invalid JSON, wrong content-type, or a required field is absent.
- **422 Unprocessable Entity**: the payload parses and has all required fields, but the values don't make sense together, e.g. trying to cancel an order that's already shipped, or setting `end_date` before `start_date`.

The distinction matters for client retry logic: a 400 usually means a client bug worth fixing before retrying, while a 422 can be a legitimate business-rule rejection the UI should surface to the user rather than treat as a bug. Validation errors include a `field` key naming which input triggered the 422.
