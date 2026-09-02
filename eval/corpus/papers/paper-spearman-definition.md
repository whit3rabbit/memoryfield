---
uuid: paper-spearman-definition
title: "Spearman correlation: rank-based measure of monotonic association"
summary: "Pearson correlation on ranks; range -1 to 1; -1 = perfectly anti-monotonic; 0 = no monotonic association; 1 = perfectly monotonic; works for ordinal data and outliers."
status: active
tags: [correlation, statistics]
source: "https://en.wikipedia.org/wiki/Spearman%27s_rank_correlation_coefficient"
---
## Answer
Spearman rho = Pearson correlation applied to ranks:
1. Rank both variables.
2. Compute Pearson on the ranks.

Properties:
- Range -1 to 1.
- Captures monotonic (not just linear) relationships.
- Robust to outliers (uses ranks, not values).
- Standard for agreement between ranking systems (e.g., two retrieval methods).
