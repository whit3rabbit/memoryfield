---
uuid: paper-gan-mode-collapse
title: "GAN: training is unstable and prone to mode collapse"
summary: "Mode collapse: G produces the same output regardless of z; G and D oscillate without convergence; many practical tricks (spectral norm, two-timescale updates) needed for stability."
status: active
tags: [gan, training, stability]
source: "https://arxiv.org/abs/1406.2661"
---
## Answer
Classic GAN training problems:
- **Mode collapse**: G learns to produce one realistic output regardless of z.
- **Oscillation**: G and D chase each other without settling.
- **Vanishing gradients**: when D is too good, G's signal disappears.

Stabilization tricks (introduced after the original paper):
- Two-timescale learning rates (D faster than G).
- Spectral normalization on D.
- Gradient penalty (WGAN-GP).
- Minibatch discrimination.
