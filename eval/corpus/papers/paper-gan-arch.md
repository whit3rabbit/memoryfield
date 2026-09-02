---
uuid: paper-gan-arch
title: "GAN: two networks trained in opposition -- generator and discriminator"
summary: "G generates fake samples from noise; D tries to distinguish real from fake; G is trained to fool D; minimax objective; alternating updates."
status: active
tags: [gan, generative, adversarial]
source: "https://arxiv.org/abs/1406.2661"
---
## Answer
Two networks:
- **Generator G**: maps noise z ~ p(z) to a sample G(z) in data space.
- **Discriminator D**: outputs P(real | x).

Minimax objective:
`min_G max_D E[log D(x)] + E[log(1 - D(G(z)))]`

In practice, G is trained to maximize `log D(G(z))` (the non-saturating variant) because the original objective's gradient vanishes early in training.
