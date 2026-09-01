---
uuid: paper-dpo-loss
title: DPO: direct preference optimization replaces RLHF's reward model + PPO
summary: Skip the reward model and the PPO loop; optimize a single classification loss directly on preference pairs (chosen, rejected); simpler, faster, often comparable quality.
status: active
tags: [dpo, rlhf, alignment]
source: https://arxiv.org/abs/2305.18290
---
## Answer
DPO loss:
```
L = -log_sigmoid(beta * (log_p(chosen|x) - log_p(rejected|x) - log_pref(chosen) + log_pref(rejected)))
```

Skips the reward model entirely. Just preference pairs `(x, y_w, y_l)` and a reference policy for KL regularization.

Empirically: matches PPO-based RLHF on many tasks with ~10x less compute and no separate reward model to train.

Limitation: weaker than PPO when high-quality preference data is abundant (RLHF's sample efficiency advantage).
