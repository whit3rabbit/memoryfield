---
uuid: sib-code-auth-oauth-state
title: Auth - how the PKCE code_verifier is generated and checked
summary: We generate a 43-character random code_verifier per login attempt, send its SHA256 challenge to the IdP up front, and the token exchange fails if the verifier doesn't hash to match.
---
## Answer
On top of `state` (see the OAuth state page), we implement PKCE for the authorization code flow. Before redirecting, we generate a 43-character URL-safe random `code_verifier`, store it in the same short-lived cookie as the nonce, and compute `code_challenge = base64url(sha256(code_verifier))` to send as a query param on the authorize request.

At token exchange time, we send the original `code_verifier` back to the IdP, which recomputes the hash and rejects the exchange if it doesn't match the `code_challenge` it received earlier. This stops an attacker who intercepts the authorization code alone from completing the exchange, since they never had the verifier.
