---
uuid: code-billing-line-math
title: "Billing: how invoice lines are computed"
summary: "Each line is `(unit_price × quantity) × proration_factor` where proration_factor is the fraction of the billing period the line covers."
status: active
tags: [billing, invoices, math]
---
## Answer
`line_total = unit_price * quantity * proration_factor`

`proration_factor` is calculated from the line's `service_start`
and `service_end` against the billing period boundaries. A line
spanning the full period has factor 1.0; a line starting halfway
through has factor 0.5.

All math uses `decimal.Decimal` with 6 decimal places of
intermediate precision. Don't use floats.

