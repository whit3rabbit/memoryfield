---
uuid: paper-vae-arch
title: VAE: encoder-decoder with a probabilistic latent space
summary: Encoder outputs mean and variance of a Gaussian posterior q(z|x); sample z from N(mu, sigma^2); decoder reconstructs x; KL term regularizes q toward N(0, I).
status: active
tags: [vae, generative, latent]
source: https://arxiv.org/abs/1312.6114
---
## Answer
VAE training:
1. Encoder: x -> (mu, log sigma^2) parameters of q(z|x).
2. Sample z = mu + sigma * eps, with eps ~ N(0, I).
3. Decoder: p(x|z) reconstructs x.
4. Loss = -E[log p(x|z)] + KL(q(z|x) || N(0, I)).

The KL term regularizes the latent space to be close to a standard Gaussian, enabling sampling at generation time.

The 'reparameterization trick' (sampling eps separately) is what makes the whole thing differentiable.
