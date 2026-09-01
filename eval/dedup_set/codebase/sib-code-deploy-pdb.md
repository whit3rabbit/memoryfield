---
uuid: sib-code-deploy-pdb
title: Deploy - how the horizontal pod autoscaler picks replica counts
summary: HPA scales each service between 2 and 20 replicas targeting 70% average CPU, with a 5-minute scale-down cooldown so traffic dips don't cause replica flapping.
---
## Answer
Autoscaling is separate from the PDB - PDB protects against disruptions, HPA decides how many replicas should exist in the first place. Each service's `HorizontalPodAutoscaler` targets 70% average CPU utilization across pods, with `minReplicas: 2` and `maxReplicas: 20` as the bounds.

Scale-up reacts fast, within about a minute of CPU crossing the target, but scale-down enforces a 5-minute stabilization window, only removing replicas if utilization has stayed low for that whole window. This avoids flapping where a brief traffic dip triggers a scale-down right before the next spike forces an immediate scale back up.
