---
uuid: code-deploy-canary-window
title: "Deploy: the canary window"
summary: "New release goes to 5% of pods for 10 minutes; if error rate < 0.5%, rolls forward; otherwise rolls back automatically."
status: active
tags: [deploy, canary]
---
## Answer
Configured in `deploy/canary.yaml`:
- 5% traffic for 10 minutes
- promotion gate: error rate < 0.5% over the window
- rollback: any of (5xx spike, latency p99 > 500ms, error budget
  burn > 2x normal)

