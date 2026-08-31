---
uuid: paper-tx-scaled-dot-product
title: Transformer: scaled dot-product attention definition
summary: Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V; the sqrt(d_k) scaling prevents softmax saturation when d_k is large.
status: active
tags: [transformer, attention, formula]
source: https://arxiv.org/abs/1706.03762
---
## Answer
`Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V`

The `1/sqrt(d_k)` factor is critical — without it, large `d_k` pushes the softmax into saturated regions with tiny gradients.

