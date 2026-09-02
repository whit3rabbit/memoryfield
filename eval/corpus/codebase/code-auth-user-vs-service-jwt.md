---
uuid: code-auth-user-vs-service-jwt
title: "Auth: the difference between user JWT and service JWT"
summary: "User JWTs have a `sub` claim with the user ID and live 1 hour; service JWTs have an `aud` claim with the service name and live 5 minutes."
status: active
tags: [auth, jwt, distinction]
---
## Answer
Two distinct JWT kinds, both signed with the same key:

- **User JWT**: `sub` = user UUID, `aud` = the service the user is
  calling, TTL = 1 hour. Issued after OAuth callback.
- **Service JWT**: no `sub`, `aud` = the calling service's own name,
  TTL = 5 minutes. Issued by `auth-tokens` from a SPIFFE SVID.

The `aud` claim is the disambiguator. A user JWT with `aud=billing`
is valid for billing endpoints; a service JWT with `aud=billing` is
for billing calling something else.

## Don't
Don't accept a JWT whose `aud` doesn't match *your* service name,
even if the signature verifies. That's the most common bug in
first-time integration code.

