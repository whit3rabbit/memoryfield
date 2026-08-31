---
uuid: code-migrations-never-drop-same-release
title: Migrations: why we never drop a column in the same release
summary: Two-release rule: release N removes all code that reads the column; release N+1 drops it. One release to find stragglers.
status: active
tags: [migrations, schema, discipline]
---
## Answer
Two-release rule. If release 47 stops reading `users.legacy_id`,
release 47 may *not* drop the column. Release 48 may.

The gap catches code paths that still read the old column —
those code paths will start erroring in release 47's logs,
giving you a release to find and fix them before the column
disappears entirely.

