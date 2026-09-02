---
uuid: paper-rope-definition
title: "RoPE: rotary position embeddings applied to query and key vectors"
summary: "Each pair of adjacent dimensions in q and k is rotated by an angle proportional to the position; the rotation matrix depends only on position, not content."
status: active
tags: [rope, positional-encoding, transformer]
source: "https://arxiv.org/abs/2104.09864"
---
## Answer
RoPE rotates q and k vectors by position-dependent angles:
```
q_i' = R(m * theta_i) * q_i
k_i' = R(n * theta_i) * k_i
```
where m, n are token positions and `theta_i = 10000^(-2i/d)`.

The key property: `q_i' . k_j'` depends only on `(m - n)`, encoding relative position implicitly.

Used in LLaMA, Mistral, Gemma, and most modern open-weight LLMs.
