---
uuid: code-billing-proration-edge
title: Billing: the proration edge case at month boundaries
summary: Lines that start or end exactly on a billing period boundary get factor 1.0 (boundary-inclusive); we use the half-open interval `(start, end]`.
status: active
tags: [billing, proration, edge-case]
source: tests/test_billing_proration.py
---
## Answer
Proration uses the half-open interval `(start, end]`. A line with
`service_start = 2026-01-01 00:00:00 UTC` and
`service_end = 2026-02-01 00:00:00 UTC` covers the entire January
period (factor 1.0), even though it touches both endpoints.

The unit tests in `test_billing_proration.py` have a matrix of all
four (start_inclusive, end_inclusive) combinations.

## Don't
Don't switch to `[start, end]` (closed) — it double-counts
midnight boundaries when two lines abut.

