---
uuid: code-api-webhook-sig
title: "API: how webhook signatures are verified"
summary: "`X-Ledger-Signature: t=<unix>,v1=<hex>`; compute HMAC-SHA256 over `t.body` with the webhook secret; reject if `|now - t| > 5min`."
status: active
tags: [api, webhooks]
---
## Answer
Webhook payload:
```
X-Ledger-Signature: t=1700000000,v1=4f3a2b1c...
```
Verify by:
1. Reject if `|now - t| > 300s` (replay protection).
2. Compute HMAC-SHA256 over `<t>.<body>` with the webhook secret.
3. Compare with `v1` using `hmac.compare_digest`.

