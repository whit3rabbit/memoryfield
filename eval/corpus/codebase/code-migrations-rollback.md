---
uuid: code-migrations-rollback
title: Migrations: how to roll back
summary: Every migration has a paired `down.sql`; the rollback path is `apply <N-1> --rollback`. Reversible migrations are the default; irreversible ones require a sign-off.
status: active
tags: [migrations, rollback]
---
## Answer
Reversible migrations: each `up.sql` has a paired `down.sql` that
exactly undoes it. Rollback is `apply <N-1> --rollback`.

Irreversible migrations (data loss, type changes) require a
documented sign-off in the PR and a `down.sql` that errors with
"irreversible — restore from backup".

