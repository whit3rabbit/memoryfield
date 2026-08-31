---
uuid: code-migrations-up-vs-expand
title: Migrations: the difference between `up` and `expand`
summary: `up` migrations change schema; `expand` migrations also deploy code that dual-writes/dual-reads; never use them interchangeably.
status: active
tags: [migrations, vocabulary]
---
## Answer
- `up.sql`: schema-only change.
- `expand.sql`: schema + code that writes the new shape (in
  parallel with the old) and/or reads from the new shape (with
  fallback to the old).
- `contract.sql`: schema + code that stops reading/writing the
  old shape.

