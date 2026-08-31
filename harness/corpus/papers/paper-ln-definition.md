---
uuid: paper-ln-definition
title: LayerNorm: normalize across features within each example
summary: Unlike BatchNorm, LayerNorm computes mean/variance per-example across the feature dimension; no batch dependency; works with variable batch sizes and RNNs.
status: active
tags: [layernorm, normalization, transformer]
source: https://arxiv.org/abs/1607.06450
---
## Answer
LayerNorm normalizes across the feature dimension for each example independently:
```
mu = mean(x, dim=features)
sigma = std(x, dim=features)
x_hat = (x - mu) / (sigma + eps)
y = gamma * x_hat + beta
```

No batch statistics are needed. This makes LayerNorm work in:
- Variable batch sizes (including batch=1).
- RNNs (where batch statistics are awkward).
- Transformers (where it became the default).
