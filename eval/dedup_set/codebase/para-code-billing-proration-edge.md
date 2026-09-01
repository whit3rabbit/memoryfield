---
uuid: para-code-billing-proration-edge
title: Billing - proration behavior right at period boundaries
summary: We treat the billing interval as half-open, (start, end], so a line touching both the start and end of a period still prorates to a full factor of 1.0.
---
## Answer
The interval used for proration math is half-open: `(start, end]`. Take a line where `service_start` is `2026-01-01 00:00:00 UTC` and `service_end` is `2026-02-01 00:00:00 UTC`. Even though both timestamps sit exactly on period boundaries, this line prorates to a factor of 1.0 because it spans the whole of January.

`test_billing_proration.py` exercises this with all four combinations of start-inclusive and end-inclusive to pin down the edge behavior.

## Don't
Resist the temptation to use a closed interval `[start, end]` instead - it causes double-counting whenever two adjacent lines meet exactly at midnight.
