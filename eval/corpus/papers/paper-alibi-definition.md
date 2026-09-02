---
uuid: paper-alibi-definition
title: "ALiBi: attention with linear biases (no position embeddings)"
summary: "Adds a non-trainable linear bias `-m * |i - j|` to attention scores; the slope m is fixed per head; no learned position embeddings needed."
status: active
tags: [alibi, positional-encoding, transformer]
source: "https://arxiv.org/abs/2108.12409"
---
## Answer
ALiBi modifies attention scores:
`score(q_i, k_j) = q_i . k_j - m_h * |i - j|`

The slope `m_h` is a fixed geometric sequence per head (no learning). Recent tokens get less penalty than distant ones, preserving order.

Used in BLOOM. Strong length extrapolation -- a model trained on 1k tokens can be evaluated on 10k+ with minimal degradation.
