---
uuid: paper-per-td-error
title: PER: prioritize replay buffer samples by TD error magnitude
summary: Sample transitions with probability proportional to |TD error|; high-error (i.e. surprising) transitions are sampled more often; importance-sampling weights correct the bias.
status: active
tags: [per, dqn, replay-buffer]
source: https://arxiv.org/abs/1511.05952
---
## Answer
Prioritized Experience Replay:
- Each transition stored with priority `p_i = |TD error| + eps`.
- Sampling probability `P(i) = p_i^alpha / Sigma p_k^alpha` (alpha=0.6 typical).
- Importance-sampling weight `w_i = (N * P(i))^(-beta)` corrects the bias introduced by non-uniform sampling (beta anneals from 0.4 to 1.0).

Result: 2x faster learning on most Atari games compared to uniform sampling.
