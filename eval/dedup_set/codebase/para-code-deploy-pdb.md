---
uuid: para-code-deploy-pdb
title: Deploy - what pod disruption budgets protect against
summary: Every service carries a PodDisruptionBudget requiring at least one pod to remain up during voluntary disruptions, stopping rolling deploys or node drains from taking the last pod down.
---
## Answer
Each service ships with a `PodDisruptionBudget` set to `minAvailable: 1`. When a voluntary disruption happens - a rolling deploy or a node drain, for instance - the Kubernetes scheduler checks the PDB first and refuses to evict a pod if doing so would leave zero pods running.

Services flagged as critical get a stricter budget: `minAvailable: 2`, or for larger fleets, a percentage figure like `60%` instead of a fixed count.
