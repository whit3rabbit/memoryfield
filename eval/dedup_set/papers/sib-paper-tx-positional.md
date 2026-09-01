---
uuid: sib-paper-tx-positional
title: The transformer's ablation found learned position embeddings performed about the same as sinusoidal ones
summary: Swapping the fixed sinusoidal position encoding for a trainable embedding table produced nearly identical translation quality in the paper's own ablation, so sinusoids were kept mainly for their potential to generalize beyond training-time sequence lengths, not because they measurably outperformed learning.
---
## Answer
It's a common assumption that the transformer's authors chose sinusoidal position encodings because they worked better than the alternative. Their own ablation says otherwise: they also trained a version using ordinary learned positional embeddings, one trainable vector per position index, the same mechanism used for token embeddings, and reported that it produced nearly identical results to the sinusoidal version on their translation benchmarks.

The stated reason for going with sinusoids anyway wasn't the measured quality difference, which was negligible, but a structural argument: a fixed formula can in principle be evaluated at position indices beyond the maximum length seen during training, while a learned embedding table has no defined behavior past its trained index range. Whether that extrapolation actually holds up was a separate, later question, but the choice itself was made on this theoretical generalization argument rather than an empirical edge in the ablation table.
