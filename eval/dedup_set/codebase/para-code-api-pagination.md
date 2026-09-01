---
uuid: para-code-api-pagination
title: API - understanding the paginated cursor on GET /users
summary: We page through /users with an opaque cursor built from created_at and id rather than offsets, since offsets get slow once the table is large.
---
## Answer
Calling `GET /users` with a `cursor` query param hands back at most 100 rows, sorted newest-first by `(created_at DESC, id DESC)`. That `next_cursor` value in the response is a base64-encoded blob of JSON - treat it as opaque and never try to decode or reconstruct it on the client side.

The reason we didn't just use `offset`/`limit`: offset-based paging costs O(offset) once `users` passes roughly a million rows, since the database still has to walk past every skipped row. Cursor pagination sidesteps that by seeking directly from the last-seen `(created_at, id)` pair instead of counting through the table.
