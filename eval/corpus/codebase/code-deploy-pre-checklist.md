---
uuid: code-deploy-pre-checklist
title: "Deploy: pre-deploy checklist"
summary: "Tests green, migrations applied to staging, dashboards reviewed, on-call notified, rollback plan documented."
status: active
tags: [deploy, checklist]
---
## Answer
- [ ] CI green for the commit being deployed
- [ ] Schema migrations tested on staging snapshot
- [ ] Dashboards reviewed for the previous 24h
- [ ] On-call notified in #deploys
- [ ] Rollback command documented in the deploy PR

