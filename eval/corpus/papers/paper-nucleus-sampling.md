---
uuid: paper-nucleus-sampling
title: Top-p (nucleus) sampling: sample from smallest set whose probabilities sum to p
summary: Sort tokens by probability; take the smallest prefix whose cumulative mass >= p; sample uniformly from that set; better than top-k at adapting to distribution shape.
status: active
tags: [sampling, nucleus, decoding]
source: https://arxiv.org/abs/1904.09751
---
## Answer
Nucleus (top-p) sampling:
1. Sort tokens by probability descending.
2. Find the smallest set V whose cumulative probability >= p.
3. Renormalize and sample from V.

p = 0.9 is a common default. Unlike top-k (fixed cutoff), top-p adapts: for sharp distributions V is small; for flat distributions V is large.
