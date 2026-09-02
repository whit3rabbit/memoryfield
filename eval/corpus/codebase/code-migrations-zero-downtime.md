---
uuid: code-migrations-zero-downtime
title: "Migrations: zero-downtime schema changes cheat sheet"
summary: "Add column → dual-write → backfill → dual-read → drop old column. Each step is a separate deploy."
status: active
tags: [migrations, reference]
---
## Answer
Five deploys to change a column's shape safely:
1. Add the new shape as a nullable column.
2. Dual-write: every write goes to both old and new.
3. Backfill: one-shot script copying old to new.
4. Dual-read: read new, fall back to old, verify the diff.
5. Drop the old column in a later release.

