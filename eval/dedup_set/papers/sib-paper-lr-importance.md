---
uuid: sib-paper-lr-importance
title: Warmup before decay - why transformers ramp the learning rate up first
summary: Training a transformer with Adam directly at its target learning rate often diverges in the first few hundred steps, because Adam's adaptive denominator is unreliable while its variance estimates are still forming; a short linear warmup phase avoids this by starting near zero and ramping up before the decay schedule takes over.
---
## Answer
Jumping straight to a target learning rate like 1e-3 or 3e-4 at step zero is a common cause of early transformer training divergence, particularly with Adam. The issue is specific to Adam's mechanics: its second-moment estimate `v` needs a number of steps to become a reliable estimate of gradient variance, and until it does, the adaptive step size `1/sqrt(v_hat)` can be much larger than intended.

Linear warmup sidesteps this by starting the learning rate near zero and increasing it linearly over some number of initial steps (commonly a few thousand for large transformer runs) before switching to the main decay schedule, whether that's cosine, linear, or another shape.

This is a distinct concern from choosing the target learning rate itself - warmup determines how safely you can approach that target, not what the target should be.
