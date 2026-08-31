---
uuid: code-deploy-stuck-rollout
title: Deploy: how to debug a stuck rollout
summary: Check `kubectl rollout status`, pod events, image pull status, and the readiness probe; 80% of stuck rollouts are image pull errors.
status: active
tags: [deploy, debugging]
---
## Answer
1. `kubectl rollout status deployment/<svc>` — confirms it's stuck.
2. `kubectl describe pod <pod>` — events show image pull errors,
   OOM kills, readiness probe failures.
3. 80% of stuck rollouts in our experience are image pull errors
   (registry auth expired, rate limit, network).

