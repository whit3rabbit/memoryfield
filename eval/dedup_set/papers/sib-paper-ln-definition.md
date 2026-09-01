---
uuid: sib-paper-ln-definition
title: Pre-LN transformer blocks train more stably than Post-LN
summary: Placing LayerNorm before the attention/FFN sublayer (Pre-LN) rather than after it (Post-LN) keeps the residual stream's gradient magnitude roughly constant through depth, letting deep transformers train without the warmup that Post-LN architectures require to avoid early divergence.
---
## Answer
The original Transformer places LayerNorm after each sublayer's residual addition (Post-LN): `x = LayerNorm(x + Sublayer(x))`. This works, but gradients through the residual stream grow with depth, and Post-LN models are known to diverge early in training unless a learning-rate warmup schedule ramps the LR up gradually over the first several thousand steps.

Pre-LN moves the normalization inside the residual branch instead: `x = x + Sublayer(LayerNorm(x))`. The residual stream itself is never normalized, so it acts as a clean gradient highway straight back to the input, and gradient magnitudes stay roughly constant regardless of depth.

The practical consequence: Pre-LN transformers can often train with a constant learning rate or a much shorter warmup, and are noticeably easier to stabilize as depth increases - one reason most modern large-scale transformer implementations default to Pre-LN.
