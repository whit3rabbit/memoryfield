---
uuid: sib-code-deploy-canary-window
title: Deploy - how blue-green cutover and instant rollback work
summary: Blue-green deploys stand up a full parallel environment, run smoke tests against it, then flip the load balancer target in one atomic step - rollback is just flipping it back.
---
## Answer
Unlike the gradual canary rollout, some services (notably `payments-api`, where a partial rollout is riskier than an all-at-once one) use blue-green deploys instead. The new version ("green") gets deployed to a fully separate, fully-scaled environment alongside the current one ("blue"), with no live traffic yet.

A smoke-test suite runs against green directly before any cutover happens. Once smoke tests pass, the load balancer's target group flips from blue to green in one atomic config change - all traffic moves at once, not gradually.

Rollback is just flipping the target group back to blue, which stays warm and running for 30 minutes post-cutover specifically so rollback is instant rather than requiring a fresh deploy.
