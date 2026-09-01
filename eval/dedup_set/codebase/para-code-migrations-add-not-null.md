---
uuid: para-code-migrations-add-not-null
title: Safely enforcing NOT NULL on an existing column
summary: Split into three migrations - add nullable column, batch-backfill 10k rows at a time, then set NOT NULL. Never combine them.
---
## Answer
Enforcing NOT NULL on a column happens across three independent
migrations, applied strictly in order and never squashed together:

1. Add the column as nullable: `ALTER TABLE users ADD COLUMN
   phone TEXT;`
2. Run an idempotent backfill script that fills the column in
   batches of 10,000 rows.
3. Once every row has a value, lock in the constraint:
   `ALTER TABLE users ALTER COLUMN phone SET NOT NULL;`

The reason for splitting is table locking. A single migration
that adds the column with a `DEFAULT` and backfills inline
rewrites every existing row as part of that one statement,
holding a lock for the entire duration on a large table. Breaking
it into steps keeps each individual migration fast.
