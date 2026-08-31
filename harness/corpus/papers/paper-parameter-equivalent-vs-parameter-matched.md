---
uuid: paper-parameter-equivalent-vs-parameter-matched
title: SwiGLU: parameter-equivalent vs parameter-matched compared to ReLU/GELU
summary: Naive SwiGLU adds an extra W_gate matrix (3 matrices vs 2); the common practice is to shrink W_1 and W_gate to 2/3 width so total params stay equal.
status: active
tags: [swiglu, parameter-count]
source: https://arxiv.org/abs/2002.05202
---
## Answer
Parameter accounting:
- Standard FFN (ReLU/GELU): 2 matrices (W_1, W_2).
- Naive SwiGLU: 3 matrices (W_1, W_gate, W_2). ~50% more params.

To match param count: set hidden dim to (8/3 * d_model) instead of 4 * d_model, which makes the 3-matrix count equal the 2-matrix count.

This is why LLaMA uses hidden_dim = (8/3) * d_model * 2 (the *2 is for SwiGLU) instead of 4 * d_model.
