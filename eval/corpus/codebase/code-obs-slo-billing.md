---
uuid: code-obs-slo-billing
title: "Observability: the SLO for billing endpoints"
summary: "99.95% availability over 30-day window; error budget is 21.6 minutes of downtime per month."
status: active
tags: [observability, slo, billing]
---
## Answer
Billing endpoints target 99.95% success rate, measured over a
30-day rolling window. The error budget is 0.05% × 30d =
~21.6 minutes/month of permitted downtime.

Below 50% budget remaining, all hands shift focus to reliability
work and freeze non-critical deploys.

