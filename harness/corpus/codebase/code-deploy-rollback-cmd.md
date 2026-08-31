---
uuid: code-deploy-rollback-cmd
title: Deploy: how to roll back a bad release
summary: `kubectl rollout undo deployment/<service>`; rollback is a forward operation and takes ~90 seconds end-to-end.
status: active
tags: [deploy, rollback]
---
## Answer
`kubectl rollout undo deployment/<service>` re-deploys the
previous image. Takes ~90s for full pod replacement at our scale.

For database-coupled rollbacks, also run
`make migrate-down <N>` if the release includes a schema change.

