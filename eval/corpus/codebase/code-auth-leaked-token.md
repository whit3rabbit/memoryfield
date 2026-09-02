---
uuid: code-auth-leaked-token
title: "Auth: handling a leaked token"
summary: "Page `#sec-incident` in Slack, run `make revoke-token <jti>`, force-rotate the affected service's identity."
status: active
tags: [auth, incident, tokens]
source: "ops/runbook/auth.md#leaked-token"
---
## Answer
1. Page `#sec-incident` in Slack.
2. Run `make revoke-token <jti>` — adds the JTI to the revocation
   list and pushes it to every edge proxy within 30s.
3. Force-rotate the affected service's workload identity (the SVID
   gets re-issued with a new serial).
4. Post-incident: review audit logs for the token's `aud` to find
   which service accepted it during the leak window.

## Don't
Don't try to revoke a single token by rotating the signing key —
that's a sledgehammer that invalidates every active session.

