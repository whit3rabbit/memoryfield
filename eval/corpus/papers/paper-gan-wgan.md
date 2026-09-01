---
uuid: paper-gan-wgan
title: GAN: Wasserstein distance formulation gives more stable training (WGAN)
summary: WGAN replaces JS divergence with Earth Mover's distance; critic (no sigmoid) outputs unbounded scores; gradient penalty enforces Lipschitz constraint.
status: active
tags: [gan, wgan, training]
source: https://arxiv.org/abs/1701.07875
---
## Answer
Wasserstein GAN (Arjovsky et al., 2017): replace the JS divergence in the original GAN objective with the Wasserstein-1 (Earth Mover's) distance.

Key changes:
- Critic (not discriminator) outputs unbounded scores.
- Weight clipping or gradient penalty enforces the 1-Lipschitz constraint.
- Loss correlates with sample quality, unlike the original GAN loss.

This makes training dynamics much more interpretable.
