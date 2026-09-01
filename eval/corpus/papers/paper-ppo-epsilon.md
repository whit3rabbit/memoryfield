---
uuid: paper-ppo-epsilon
title: PPO: clipping epsilon controls how far the new policy can drift
summary: epsilon=0.2 in the original paper; lower epsilon (0.1) for more conservative updates; higher (0.3) for faster but riskier updates.
status: active
tags: [ppo, hyperparameter]
source: https://arxiv.org/abs/1707.06347
---
## Answer
epsilon in the PPO clip controls trust-region size:
- 0.1: conservative, more updates needed.
- 0.2: paper default, robust across tasks.
- 0.3: aggressive, faster learning on stable tasks, less robust.

Don't tune this before tuning the learning rate. LR matters more.
