---
uuid: paper-bn-formula
title: BatchNorm: normalize activations per mini-batch during training
summary: x_hat = (x - mu_B) / sqrt(sigma^2_B + eps); scale and shift: y = gamma * x_hat + beta; mu_B and sigma^2_B are batch statistics; running averages maintained for inference.
status: active
tags: [batchnorm, normalization, training]
source: https://arxiv.org/abs/1502.03167
---
## Answer
Per mini-batch:
1. Compute batch mean `mu_B` and variance `sigma^2_B`.
2. Normalize: `x_hat = (x - mu_B) / sqrt(sigma^2_B + eps)`.
3. Scale and shift: `y = gamma * x_hat + beta`.

During training, maintain exponential moving averages of `mu_B` and `sigma^2_B` for inference.

## Don't
Don't apply BatchNorm before the very first layer -- there's no benefit and it can destabilize early training.
