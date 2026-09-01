---
uuid: code-deploy-log-format
title: Deploy: the deploy log format
summary: Each deploy emits a structured log with `deploy_id, service, image, sha, deployer, started_at, completed_at`; queries against this drive the deploy dashboard.
status: active
tags: [deploy, observability]
---
## Answer
```
deploy_id: dpl_2026_03_15_billing_a7c9d2e
service: billing
image: billing:a7c9d2e
sha: a7c9d2e
deployer: alice
started_at: 2026-03-15T14:32:00Z
completed_at: 2026-03-15T14:33:30Z
```

