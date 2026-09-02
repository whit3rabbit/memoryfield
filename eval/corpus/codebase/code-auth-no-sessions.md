---
uuid: code-auth-no-sessions
title: "Auth: why we don't use sessions"
summary: "Sessions require server-side state; JWTs are stateless and let us scale auth-free at the edge."
status: active
tags: [auth, design, sessions]
---
## Answer
We use stateless JWTs because:
1. The edge proxy can verify tokens without a database round-trip.
2. There's no session store to shard, replicate, or evict.
3. Logout is just "client deletes the token" — for our threat
   model (low-value sessions, short TTLs) this is fine.

The tradeoff: revocation is coarser (full key rotation) than
per-session invalidation. We mitigate with short TTLs (1 hour user,
5 minutes service).

