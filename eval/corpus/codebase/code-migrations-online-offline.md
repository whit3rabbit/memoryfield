---
uuid: code-migrations-online-offline
title: "Migrations: online vs offline schema changes"
summary: "Online (concurrent index creation, NOT NULL via check constraint) takes longer but doesn't lock; offline takes seconds but blocks all writes."
status: active
tags: [migrations, schema]
---
## Answer
Two modes:
- **Online**: uses Postgres features that don't take an
  ACCESS EXCLUSIVE lock. Safe to run during peak traffic.
  Examples: `CREATE INDEX CONCURRENTLY`, adding NOT NULL via a
  CHECK constraint then validating.
- **Offline**: takes the heavy lock briefly. Faster but causes
  write-stall on large tables. Used only when online isn't
  possible (e.g., changing a column's TYPE).

