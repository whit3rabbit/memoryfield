---
uuid: sib-code-auth-aud-meaning
title: Auth - how service token scope claims restrict access
summary: The scope claim on service-to-service JWTs is a space-separated list of resource-verb pairs like orders-read, and inventory rejects any request whose scope doesn't cover the action.
---
## Answer
Service tokens carry a `scope` claim in addition to `aud` - a space-separated string like `orders-read orders-write`. Each downstream service maintains its own allowlist of scopes it understands; a request whose token lacks the scope for the attempted action gets a 403, even if `aud` matches correctly.

Scopes are assigned per calling-service identity in `auth-tokens`' config, not requested dynamically by the caller. If `billing` needs a new scope against `inventory`, someone has to add it to `auth-tokens`' service registry and redeploy that service - there's no self-service scope escalation path.
