---
uuid: code-billing-trial
title: Billing: how trial periods are billed
summary: Trials generate zero-amount invoice lines with `proration_factor = 0`; they exist only for audit trail.
status: active
tags: [billing, trial]
---
## Answer
Trials create invoice lines with `quantity = 0` (or `unit_price = 0`,
depending on the line type). The line is still emitted and
finalized, so the audit trail shows "customer was on trial
2026-03-01 to 2026-03-15" even though no money changed hands.

