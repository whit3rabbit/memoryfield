---
uuid: sib-code-billing-proration-edge
title: Billing - when a mid-cycle plan change takes effect
summary: Upgrades apply immediately with a prorated charge for the rest of the period, while downgrades queue until the next billing cycle so the customer keeps what they already paid for.
---
## Answer
Plan changes are asymmetric by design. An **upgrade** (moving to a plan with a higher price) takes effect the moment the customer confirms it. We prorate the price difference for the remainder of the current period and charge it immediately.

A **downgrade** instead gets queued as a pending change and only applies at the start of the next billing cycle. We don't refund the difference for the current period, since the customer already paid for and had access to the higher tier's features through the period they purchased.

Canceling a pending downgrade before the cycle rolls over is a no-op cost-wise - it just removes the queued change, no charge either way.
