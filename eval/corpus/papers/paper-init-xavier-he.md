---
uuid: paper-init-xavier-he
title: "Weight initialization: Xavier and He (Kaiming)"
summary: "Xavier: variance ~ 1/fan_in for tanh/sigmoid. He: variance ~ 2/fan_in for ReLU. Wrong init causes vanishing/exploding gradients."
status: active
tags: [initialization, training, fundamentals]
source: "https://arxiv.org/abs/1502.01852"
---
## Answer
Two common defaults:

**Xavier (Glorot)**: `Var(W) = 1/fan_in` or `2/(fan_in + fan_out)`. Best for tanh / sigmoid activations.

**He (Kaiming)**: `Var(W) = 2/fan_in`. Best for ReLU / leaky ReLU.

Modern transformers typically use smaller init schemes (GPT-2 style: `std = 0.02`) and rely on LayerNorm to control magnitudes.
