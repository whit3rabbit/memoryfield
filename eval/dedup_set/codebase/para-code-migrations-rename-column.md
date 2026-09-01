---
uuid: para-code-migrations-rename-column
title: Renaming a column without downtime
summary: Expand-contract over four releases - add and dual-write, dual-read favoring new, stop writing old, drop old. About six weeks total.
---
## Answer
Column renames use expand-contract spread across four releases
rather than a single `RENAME COLUMN` statement:

- **N**: introduce `users.display_name` alongside the existing
  `users.name`, writing to both, and backfill `display_name` for
  existing rows.
- **N+1**: switch reads to prefer `display_name`, falling back to
  `name` where it's still missing, while application code is
  migrated over gradually.
- **N+2**: stop writing to `name` entirely - it becomes dead
  weight kept only as a rollback safety net.
- **N+3**: drop `users.name` once the team is confident nothing
  needs it. We typically leave six weeks between N+2 and N+3.

A straight rename breaks any deployed code still expecting the
old name, which is what this sequence avoids.
