---
uuid: code-billing-refunds
title: Billing: handling refunds
summary: Refunds are negative invoice lines with a `refund_of` reference to the original line; they don't modify the original line.
status: active
tags: [billing, refunds]
---
## Answer
A refund creates a *new* invoice line with a negative amount and
a `refund_of` foreign key to the original line. We never modify
the original line.

This preserves the audit trail: a customer can see exactly what
they were charged and exactly what was refunded, in order.

