---
uuid: para-paper-gan-wgan
title: WGAN swaps JS divergence for Earth Mover's distance
summary: Arjovsky et al.'s 2017 Wasserstein GAN replaces the original GAN's Jensen-Shannon objective with the Wasserstein-1 distance, uses an unbounded-output critic instead of a sigmoid discriminator, and enforces a Lipschitz constraint via weight clipping or a gradient penalty, producing a loss that actually tracks sample quality.
---
## Answer
The original GAN objective minimizes Jensen-Shannon divergence between the real and generated distributions, which provides poor gradients once the two distributions have little overlap - a common state early in training. WGAN (Arjovsky, Chintala, Bottou, 2017) swaps this for the Wasserstein-1 (Earth Mover's) distance, which stays informative even when the distributions barely overlap.

Implementing this requires two changes to the network. The discriminator becomes a critic: it drops its final sigmoid and outputs an unbounded real-valued score rather than a probability. And because the Wasserstein formulation is only valid under a 1-Lipschitz constraint on the critic, that constraint has to be enforced explicitly, either by clipping the critic's weights to a small range or via a gradient penalty term.

The practical payoff: unlike the original GAN's loss curve, the WGAN critic's loss correlates with actual sample quality, making training progress something you can read off a graph.
