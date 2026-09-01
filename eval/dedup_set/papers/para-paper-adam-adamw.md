---
uuid: para-paper-adam-adamw
title: AdamW decouples weight decay from the adaptive gradient scaling
summary: Adding L2 penalty directly to Adam's gradient causes uneven shrinkage since it gets divided by sqrt(v_hat); AdamW instead subtracts weight decay after the adaptive update, and this decoupled version is now the standard optimizer for transformers.
---
## Answer
Standard Adam folds L2 regularization into the gradient before computing the adaptive step. Because the adaptive denominator `sqrt(v_hat)` varies per parameter, that regularization term ends up scaled unevenly - large-variance parameters get shrunk less than they should, small-variance parameters more.

Loshchilov and Hutter's 2019 fix (AdamW) moves weight decay outside the adaptive update entirely: `θ_t = θ_{t-1} - α * m_hat / (sqrt(v_hat) + ε) - α * λ * θ_{t-1}`. The decay term no longer passes through `v_hat`, so every parameter shrinks by the same proportional amount.

Nearly every transformer training recipe today uses AdamW rather than plain Adam with L2 penalty, precisely because of this uniform-shrinkage property.
