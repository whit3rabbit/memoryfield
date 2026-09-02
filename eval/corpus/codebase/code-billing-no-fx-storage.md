---
uuid: code-billing-no-fx-storage
title: "Billing: why we don't store currency conversions"
summary: "We charge in the customer's billing currency; conversions happen at payout time via the recorded FX rate snapshot."
status: active
tags: [billing, currency, fx]
---
## Answer
Invoice amounts are stored in the customer's billing currency.
When we pay out to the customer's bank in a different currency,
we apply the FX rate at the time of payout, not at invoice time.

This means we never need to retroactively adjust invoices when
exchange rates move — a regulator-friendly property.

## Don't
Don't compute the converted amount at invoice time and store it.
That creates an FX-adjustment line item that auditors hate.

