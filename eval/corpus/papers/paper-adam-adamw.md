---
uuid: paper-adam-adamw
title: "Adam: weight decay should be decoupled (AdamW) for best results"
summary: "L2 regularization in Adam interacts with the adaptive step size; decoupled weight decay (AdamW, Loshchilov & Hutter 2019) treats weight decay separately from the gradient."
status: active
tags: [adam, adamw, regularization]
source: "https://arxiv.org/abs/1711.05101"
---
## Answer
Original Adam applies L2 regularization by adding it to the gradient. With Adam's adaptive step size, this regularization is *scaled* by `1/sqrt(v_hat)`, producing non-uniform shrinkage across parameters.

AdamW (Loshchilov & Hutter, 2019) decouples weight decay: `θ_t = θ_{t-1} - α * m_hat / (sqrt(v_hat) + ε) - α * λ * θ_{t-1}`.

This gives uniform shrinkage. AdamW is the default in essentially all modern transformer training.
