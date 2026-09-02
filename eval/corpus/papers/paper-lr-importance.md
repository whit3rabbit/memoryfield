---
uuid: paper-lr-importance
title: "Learning rate: the most important hyperparameter"
summary: "Too high: loss oscillates or diverges. Too low: slow convergence, gets stuck. Right: loss decreases smoothly. Default for Adam is 1e-3; for SGD with momentum is 1e-1."
status: active
tags: [learning-rate, training, hyperparameter]
source: "https://arxiv.org/abs/1506.01186"
---
## Answer
The single most consequential hyperparameter.

Symptoms of wrong LR:
- Too high: loss spikes, NaN, model diverges.
- Too low: loss decreases but plateaus before fitting.

Defaults:
- Adam: 1e-3
- SGD with momentum: 1e-1
- LLaMA-style: 3e-4 with cosine schedule

LR schedulers (cosine, linear warmup + decay) almost always beat constant LR.
