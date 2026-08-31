---
uuid: code-migrations-audit-log
title: Migrations: the audit log table
summary: Every migration records `(migration_id, applied_at, applied_by, sha256, reverted: bool)` in `schema_migrations`; never delete rows.
status: active
tags: [migrations, audit]
---
## Answer
`schema_migrations` is append-only:
```
migration_id | applied_at | applied_by | sha256 | reverted
```

Rows are never deleted (even for reverted migrations). The
`reverted` flag distinguishes forward and back.

