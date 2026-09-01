---
uuid: sib-paper-adam-adamw
title: Adam's bias correction terms fix zero-init skew in early steps
summary: Adam initializes the first and second moment estimates at zero, so raw m and v are biased toward zero early in training; dividing by (1 - beta1^t) and (1 - beta2^t) produces m_hat and v_hat, correcting that bias for the first few hundred steps.
---
## Answer
Adam maintains two exponential moving averages: `m` (first moment, the gradient mean) and `v` (second moment, the gradient variance). Both are initialized to zero vectors.

Because the moving-average update `m_t = beta1 * m_{t-1} + (1 - beta1) * g_t` starts from zero, early estimates are biased toward zero, especially with the common defaults beta1=0.9 and beta2=0.999, since the correction decays slowly.

Adam corrects for this with bias-corrected estimates: `m_hat = m_t / (1 - beta1^t)` and `v_hat = v_t / (1 - beta2^t)`. At t=1 this divides by a small number, inflating the raw estimate back to an unbiased scale; as t grows the correction factor approaches 1 and has no effect.

Without this correction, the first several hundred updates would take artificially small steps.
