---
uuid: paper-moe-load-balancing
title: "MoE: load balancing loss prevents expert collapse"
summary: "Auxiliary loss penalizes uneven routing across experts; without it, the router converges to sending all tokens to a few experts (collapse)."
status: active
tags: [moe, load-balancing, training]
source: "https://arxiv.org/abs/2101.03961"
---
## Answer
Without balancing, the router learns to favor a few 'good' experts, leaving others unused -- destroying the capacity benefit.

Auxiliary loss (Switch Transformer, Fedus et al., 2022):
```
loss_balance = alpha * N * sum(f_i * P_i)
```
where `f_i` is the fraction of tokens routed to expert i and `P_i` is the average routing probability. Minimized when tokens are uniformly distributed.

Typical `alpha = 0.01`.
