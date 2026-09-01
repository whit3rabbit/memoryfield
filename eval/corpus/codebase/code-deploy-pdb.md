---
uuid: code-deploy-pdb
title: Deploy: how pod disruption budgets work
summary: PDB `minAvailable=1` ensures at least one pod stays up during voluntary disruptions; protects against rolling deploys that drain too aggressively.
status: active
tags: [deploy, k8s]
---
## Answer
Every service has a `PodDisruptionBudget` of `minAvailable: 1`.
During voluntary disruptions (rolling deploy, node drain), the
scheduler respects the PDB and won't evict the last pod.

For critical services the PDB is `minAvailable: 2` (or
percentages like `60%` for larger deployments).

