---
uuid: paper-ppo-clipped-objective
title: "PPO: clipped surrogate objective prevents destructively large policy updates"
summary: "ratio = exp(new_logp - old_logp); objective = min(ratio * advantage, clip(ratio, 1-eps, 1+eps) * advantage); eps=0.2 default."
status: active
tags: [ppo, rl, policy-gradient]
source: "https://arxiv.org/abs/1707.06347"
---
## Answer
PPO's clipped objective:

```
ratio = exp(log_prob_new - log_prob_old)
objective = min(ratio * advantage,
                clip(ratio, 1 - eps, 1 + eps) * advantage)
```

The `clip` term removes incentive to move `ratio` outside `[1-eps, 1+eps]`, keeping updates close to the old policy. Default `eps = 0.2`.

This is simpler than TRPO (which uses a KL constraint with a Hessian) and empirically comparable in performance.
