---
uuid: code-billing-tax-inclusive
title: "Billing: what `tax_mode: inclusive` means"
summary: "Prices already include tax; the invoice's `tax` field is computed as `total - subtotal / (1 + tax_rate)`."
status: active
tags: [billing, tax]
---
## Answer
`tax_mode: inclusive` means the listed prices contain tax already
(common in EU B2C). To back out the tax portion:
`tax = total - subtotal / (1 + tax_rate)`.

Compare to `tax_mode: exclusive` (US B2B) where
`tax = subtotal * tax_rate`.

