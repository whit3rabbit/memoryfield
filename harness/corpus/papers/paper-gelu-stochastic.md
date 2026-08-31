---
uuid: paper-gelu-stochastic
title: GELU: smoother than ReLU; stochastic regularization interpretation
summary: Can be interpreted as multiplying x by a Bernoulli mask with probability Phi(x); the stochastic view explains why it generalizes better than ReLU.
status: active
tags: [gelu, activation, theory]
source: https://arxiv.org/abs/1606.08415
---
## Answer
GELU(x) = x * P(X <= x) where X ~ N(0, 1).

Stochastic interpretation: mask x with a Bernoulli random variable that takes value 1 with probability Phi(x). This is a smoother (non-binary) version of dropout-on-the-input.
