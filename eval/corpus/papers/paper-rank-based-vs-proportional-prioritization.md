---
uuid: paper-rank-based-vs-proportional-prioritization
title: "PER: rank-based vs proportional prioritization"
summary: "Two variants: rank-based uses the rank in |TD error| order (robust to outliers); proportional uses raw |TD error| (faster but sensitive to outliers). Rank-based is more common."
status: active
tags: [per, variants]
source: "https://arxiv.org/abs/1511.05952"
---
## Answer
Two prioritization schemes:
- **Proportional**: `p_i = |TD_i| + eps`. Sensitive to outlier errors.
- **Rank-based**: `p_i = 1 / rank(i)` where rank is by |TD error|. More robust.

The original paper found rank-based slightly better on most Atari games. Most implementations use rank-based by default.
