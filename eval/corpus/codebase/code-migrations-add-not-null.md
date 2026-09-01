---
uuid: code-migrations-add-not-null
title: Migrations: how to add a NOT NULL column safely
summary: Three-step: add nullable column, backfill in batches, set NOT NULL. Each step is its own migration; never combine.
status: active
tags: [migrations, schema, safety]
---
## Answer
Three separate migrations, applied in order:

1. `ALTER TABLE users ADD COLUMN phone TEXT;` (nullable)
2. Backfill script in batches of 10k rows, idempotent.
3. `ALTER TABLE users ALTER COLUMN phone SET NOT NULL;`

Combining these into one migration locks the table for the full
backfill duration on large tables.

## Don't
Don't use a single `ALTER TABLE` with a DEFAULT for the backfill —
it rewrites every row in place.

