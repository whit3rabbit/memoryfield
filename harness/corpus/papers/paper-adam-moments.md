---
uuid: paper-adam-moments
title: Adam: adaptive moments combine momentum and RMSProp
summary: First moment m_t = EMA of gradients (momentum-like); second moment v_t = EMA of squared gradients (RMSProp-like); bias-corrected; default betas = 0.9, 0.999.
status: active
tags: [adam, optimizer, training]
source: https://arxiv.org/abs/1412.6980
---
## Answer
Adam maintains two moving averages:
- `m_t = β1 * m_{t-1} + (1 - β1) * g_t` (first moment, like momentum)
- `v_t = β2 * v_{t-1} + (1 - β2) * g_t^2` (second moment, like RMSProp)

Bias correction: `m_hat = m_t / (1 - β1^t)`, `v_hat = v_t / (1 - β2^t)`.

Update: `θ_t = θ_{t-1} - α * m_hat / (sqrt(v_hat) + ε)`.

Defaults: `β1=0.9`, `β2=0.999`, `ε=1e-8`.
