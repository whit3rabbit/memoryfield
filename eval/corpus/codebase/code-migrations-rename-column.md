---
uuid: code-migrations-rename-column
title: "Migrations: how to rename a column safely"
summary: "Three-release sequence: add new column, dual-write from old, backfill, dual-read with old-precedence, drop old. ~6 weeks."
status: active
tags: [migrations, schema, rename]
---
## Answer
The expand-contract pattern, three releases:
- **Release N**: add `users.display_name`; keep writing to
  `users.name`. Backfill `display_name` once.
- **Release N+1**: write to both; read from `display_name` with
  fallback to `name`. Update application code gradually.
- **Release N+2**: stop writing to `name`; the wait period
  before drop is your call (we use 6 weeks).
- **Release N+3**: drop `users.name`.

