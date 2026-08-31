---
uuid: code-migrations-test-destructive
title: Migrations: testing a destructive change
summary: Restore prod snapshot to staging, run the migration, run the full integration suite, then run a sampling query to confirm row counts match.
status: active
tags: [migrations, testing]
---
## Answer
1. Take a prod snapshot from last night's backup, restore to staging.
2. Apply the migration to staging.
3. Run `make test-integration-staging` — full suite against real-
   ish data.
4. Spot-check row counts on the top 10 tables against prod.

Don't trust migrations that have only been tested against a
10-row development database.

