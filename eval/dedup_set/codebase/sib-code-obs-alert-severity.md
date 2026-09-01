---
uuid: sib-code-obs-alert-severity
title: Observability - muting alerts during planned maintenance
summary: Mute windows are scoped to a service and tag, auto-expire after 4 hours by default, and P1 pages always bypass them.
---
## Answer
Planned maintenance (deploys, database migrations, load tests)
creates noisy but expected alerts, so on-call can mute a specific
service ahead of time rather than acknowledging pages one by one.

A mute is scoped by `service` and an optional `tag` (for example
`service=payments-api, tag=migration`), created from the alerting
dashboard or via `mutectl create --service payments-api --minutes
120`. Mutes default to a 4-hour auto-expiry so a forgotten mute
cannot silence real problems indefinitely, and the maximum
allowed duration is 24 hours, requiring a second approver beyond
that.

One exception: P1 alerts always page regardless of any active
mute, since a mute is meant to suppress expected noise, not to
mask a genuine outage during a maintenance window.
