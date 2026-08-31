---
uuid: paper-flashattn-online-softmax
title: FlashAttention: online softmax trick handles block-wise computation
summary: Standard softmax needs the full row to compute the denominator; FlashAttention tracks running max and sum so partial blocks can be rescaled correctly.
status: active
tags: [flashattention, softmax, numerics]
source: https://arxiv.org/abs/2205.14135
---
## Answer
Standard softmax: `softmax(x_i) = exp(x_i) / Σ exp(x_j)` — needs the full row.

Online softmax (Milakov & Gimelshein, 2018) tracks:
- `m_i = max(m_{i-1}, x_i)`
- `ℓ_i = ℓ_{i-1} * exp(m_{i-1} - m_i) + exp(x_i - m_i)`

The accumulated max and sum let you rescale partial outputs correctly when new blocks arrive. FlashAttention uses this to compute the tiled softmax without ever holding the full matrix.
