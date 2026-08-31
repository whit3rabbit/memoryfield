---
uuid: paper-adam-default-lr
title: Adam: default learning rate is 1e-3 (much higher than SGD's 1e-2 batch-size-scaled)
summary: Adam's per-parameter adaptive scaling means the global LR is interpretable; 1e-3 is a good starting point; SGD typically uses 1e-1 with momentum.
status: active
tags: [adam, learning-rate]
source: https://arxiv.org/abs/1412.6980
---
## Answer
Adam's default LR (1e-3) is roughly an order of magnitude lower than SGD-with-momentum's typical LR (1e-1).

This is because Adam's per-parameter scaling absorbs part of what the global LR does in SGD.

When switching optimizers, scale LR appropriately.
