---
uuid: code-obs-dashboard-naming
title: "Observability: dashboard naming convention"
summary: "Service-name first, then use case (e.g., `billing: latency`, `billing: errors`); one dashboard per service + use case pair, never per query."
status: active
tags: [observability, dashboards]
---
## Answer
`<service>: <use-case>` (e.g., `billing: latency`,
`auth: token issuance`). One dashboard per (service, use-case)
pair.

## Don't
Don't make a "kitchen sink" dashboard with everything. Those
never load and nobody reads them.

