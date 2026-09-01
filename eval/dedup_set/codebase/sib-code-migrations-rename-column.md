---
uuid: sib-code-migrations-rename-column
title: Changing a column's type without downtime
summary: Dual-write to a new typed column, backfill, cut reads over, then drop the old column - about four weeks end to end.
---
## Answer
Changing a column's underlying type (for example `orders.total`
from `INTEGER` to `BIGINT`) does not use `ALTER COLUMN ... TYPE`
directly, since that rewrites the table and locks it. Instead:

- **Release N**: add `orders.total_v2` with the new type, dual-write
  it alongside `orders.total`, and backfill existing rows in
  batches.
- **Release N+1**: switch application reads to `total_v2`, keeping
  the dual write as a safety net.
- **Release N+2**: after about four weeks with no issues, stop
  writing `orders.total` and drop it, optionally renaming
  `total_v2` back to `total` in a follow-up migration.

This pattern differs from a plain rename because the two columns
never hold interchangeable values mid-migration - `total_v2` may
briefly diverge if a backfill batch is still catching up, so reads
always prefer it once cutover happens.
