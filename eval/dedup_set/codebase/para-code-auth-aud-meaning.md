---
uuid: para-code-auth-aud-meaning
title: Auth - who the aud claim actually identifies
summary: The aud claim names the service meant to receive the token, not the one that issued it - always set it to whatever the request is being sent to.
---
## Answer
People frequently get `aud` backwards. It identifies the *recipient* service - the one that should accept the token - not the service that created it.

Concretely: when `billing` needs to call `inventory`, it asks `auth-tokens` to mint a JWT with `aud=inventory`. When `inventory` receives that request, it checks the token's `aud` against its own service name and accepts it because they match.

## Don't
Never point `aud` at the service making the call. That mistake tends to come from a SAML background, where `AudienceRestriction` semantics work a bit differently than JWT `aud` does here.
