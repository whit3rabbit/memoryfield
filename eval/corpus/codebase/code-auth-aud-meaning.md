---
uuid: code-auth-aud-meaning
title: "Auth: what `aud` claims mean in practice"
summary: "`aud` is the service *receiving* the token, not the service *issuing* it; check the API docs for what each endpoint expects."
status: active
tags: [auth, jwt, aud]
---
## Answer
`aud` (audience) names the service that should accept the token.
For service-to-service auth, this is the service the calling code
is going to make a request *to*.

Example: when `billing` calls `inventory`, billing asks `auth-tokens`
for a JWT with `aud=inventory`. inventory accepts it because the
`aud` matches its own name.

## Don't
Don't set `aud` to the calling service's own name. This is a
common confusion from people used to SAML `AudienceRestriction`
where the semantics are slightly different.

