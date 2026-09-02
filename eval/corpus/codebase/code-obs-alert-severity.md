---
uuid: code-obs-alert-severity
title: "Observability: the alerting severity ladder"
summary: "P5 = info (logged); P4 = warning (Slack); P3 = page primary on-call; P2 = page secondary; P1 = wake everyone."
status: active
tags: [observability, alerting]
---
## Answer
- **P5**: logged, no notification.
- **P4**: Slack channel, no page.
- **P3**: page primary on-call.
- **P2**: page secondary on-call (still up after 15 min).
- **P1**: page everyone on the team + incident commander.

