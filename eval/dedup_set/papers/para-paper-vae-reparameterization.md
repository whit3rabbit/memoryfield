---
uuid: para-paper-vae-reparameterization
title: The reparameterization trick moves the random draw outside the gradient path
summary: Instead of sampling z directly from N(mu, sigma^2), a VAE samples a fixed-distribution noise term eps ~ N(0, I) and computes z = mu + sigma * eps, so backprop can flow through mu and sigma while eps is treated as a constant.
---
## Answer
A VAE's encoder outputs a mean mu and standard deviation sigma describing a distribution over the latent code, and the decoder needs an actual sample z from that distribution to reconstruct the input. The naive approach, sampling z directly from N(mu, sigma^2) inside the network, breaks backpropagation: sampling is not a differentiable operation, so gradients can't pass through it back to mu and sigma.

The fix separates the randomness from the learned parameters. Draw eps from a fixed, parameter-free distribution N(0, I), then compute z = mu + sigma * eps as an ordinary arithmetic operation. Since eps doesn't depend on the network's weights, it can be treated as a constant during the backward pass, and the multiplication and addition that produce z are both differentiable with respect to mu and sigma. The stochasticity still exists (a new eps is drawn every forward pass), it's just been relocated to a spot where it doesn't block gradient flow.
