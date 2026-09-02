---
uuid: paper-rope-relative
title: "RoPE: relative position emerges from absolute rotations"
summary: "The dot product of rotated q and k depends only on their relative distance (m - n), not on absolute positions; this gives length extrapolation properties."
status: active
tags: [rope, theory]
source: "https://arxiv.org/abs/2104.09864"
---
## Answer
Algebraic property: for RoPE-rotated vectors q_m and k_n,
`<q_m, k_n> = f(q, k, m - n)`

i.e., the attention score depends only on the relative position, not on where in the sequence each token sits.

This implicit relative-position encoding enables length extrapolation better than absolute position embeddings.
