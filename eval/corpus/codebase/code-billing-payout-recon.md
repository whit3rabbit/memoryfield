---
uuid: code-billing-payout-recon
title: "Billing: the payout reconciliation job"
summary: "Runs daily at 02:00 UTC; matches ledger entries against Stripe payouts and flags discrepancies > $0.01."
status: active
tags: [billing, payout, job]
---
## Answer
`payout-reconciler` runs as a cron at 02:00 UTC daily. It reads
Stripe's payout report, joins against our `ledger_entries` table
on the Stripe transaction ID, and writes any mismatch > $0.01 to
`payout_discrepancies` for manual review.

Tolerance of $0.01 is intentional — FX rounding between charge
and payout can produce sub-cent noise.

