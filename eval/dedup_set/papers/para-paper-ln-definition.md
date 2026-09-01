---
uuid: para-paper-ln-definition
title: LayerNorm normalizes each example over its own features
summary: Instead of computing mean and variance across a batch like BatchNorm, LayerNorm computes them per-example across the feature dimension, so it needs no batch statistics and works identically at batch size 1, in RNNs, and in transformers.
---
## Answer
LayerNorm computes its normalization statistics differently from BatchNorm: for each individual example, it takes the mean and standard deviation across that example's own feature dimension, not across the batch.

```
mu = mean(x, dim=features)
sigma = std(x, dim=features)
x_hat = (x - mu) / (sigma + eps)
y = gamma * x_hat + beta
```

Because the computation never looks outside a single example, LayerNorm has no dependency on batch composition or batch size at all. That property is what makes it usable in three settings where BatchNorm struggles: batch size 1, recurrent networks (where batch statistics vary awkwardly step to step), and transformers, where it has become the standard normalization layer.
