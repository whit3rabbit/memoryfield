---
uuid: para-code-auth-oauth-state
title: Auth - verifying the OAuth state parameter on callback
summary: Before sending a user to the identity provider we drop a signed nonce in a state cookie, then check it against the returned state with a constant-time comparison.
---
## Answer
Right before redirecting a user off to the IdP, we mint a 128-bit random nonce, sign it with HMAC-SHA256, and store it as the `oauth_state` cookie. When the IdP redirects back, we take the `state` query param from that callback and compare it to the cookie's value using `hmac.compare_digest`, which avoids timing side-channels.

The signing key is the same Ed25519 key used for JWTs elsewhere, just operated in HMAC mode - a bit of a stretch for this use case, but fine given the threat model.

## Don't
Don't move this state into a server-side session - that would create a session record for every visitor who never even finishes logging in, an easy way to flood the session store.
