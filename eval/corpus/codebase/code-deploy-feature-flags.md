---
uuid: code-deploy-feature-flags
title: "Deploy: feature flag rollout order"
summary: "Internal users → 1% → 10% → 50% → 100%; each step waits ≥24 hours and requires no SLO regression."
status: active
tags: [deploy, feature-flags]
---
## Answer
Gradual rollout percentages: 0, 1, 10, 50, 100. Gating criteria:
- Each step ≥ 24 hours
- No SLO regression on p99 latency or error rate
- Manual checkpoint at 50% (review dashboards)

