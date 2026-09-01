---
uuid: sib-code-migrations-add-not-null
title: Safely dropping a column nobody reads anymore
summary: Four-stage deprecation - stop reading, stop writing, wait two weeks, then drop the column in its own migration.
---
## Answer
Dropping a column follows a slower, four-stage sequence so a
rollback never needs the data back:

1. Confirm no application code reads the column and remove any
   remaining read paths.
2. Stop writing to it (remove it from insert and update
   statements) while leaving the column in place.
3. Wait two weeks with the column unused but present, watching
   error rates and any downstream jobs that might still reference
   it directly.
4. Drop it: `ALTER TABLE orders DROP COLUMN legacy_status;` in
   its own migration.

The wait period exists because a fast rollback (redeploying the
previous app version) needs the column to still exist. Dropping
too early turns a routine rollback into a data-recovery incident.
