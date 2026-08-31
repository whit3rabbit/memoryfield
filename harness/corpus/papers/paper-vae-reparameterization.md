---
uuid: paper-vae-reparameterization
title: VAE: reparameterization trick makes sampling differentiable
summary: z = mu + sigma * eps, with eps ~ N(0, I); sampling eps outside the gradient path lets gradients flow through mu and sigma.
status: active
tags: [vae, reparameterization]
source: https://arxiv.org/abs/1312.6114
---
## Answer
Without the reparameterization trick, sampling z ~ N(mu, sigma^2) inside the forward pass would block gradient flow (the sampling op isn't differentiable).

The trick: `z = mu + sigma * eps` where `eps ~ N(0, I)`. The randomness is now in eps, which is treated as a constant during backprop. Gradients flow through mu and sigma normally.
