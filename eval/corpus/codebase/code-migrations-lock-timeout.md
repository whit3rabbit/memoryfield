---
uuid: code-migrations-lock-timeout
title: "Migrations: the `lock_timeout` setting"
summary: "Set `lock_timeout = '5s'` at the top of every migration; migration aborts if it can't acquire the lock in 5 seconds, avoiding queue buildup."
status: active
tags: [migrations, ops, safety]
---
## Answer
Every migration file starts with
`SET lock_timeout = '5s';`

If the migration can't get the lock it needs within 5s, it errors
out. The migration runner retries with exponential backoff. This
prevents a slow migration from blocking other migrations behind it
in the queue.

