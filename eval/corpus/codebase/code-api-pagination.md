---
uuid: code-api-pagination
title: API: why GET /users returns paginated cursors
summary: Cursor-based pagination on `created_at + id`; `next_cursor` is opaque, don't parse it; offsets would be O(n) on large tables.
status: active
tags: [api, pagination]
---
## Answer
`GET /users?cursor=<opaque>` returns up to 100 results ordered
by `(created_at DESC, id DESC)`. The cursor is an opaque
base64-encoded JSON; do not parse it client-side.

Offset pagination would be O(offset) on `users` once it grows
past ~1M rows.

