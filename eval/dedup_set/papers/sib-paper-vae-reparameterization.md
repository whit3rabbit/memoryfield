---
uuid: sib-paper-vae-reparameterization
title: The VAE loss pairs a reconstruction term with a KL penalty toward a standard normal prior
summary: A VAE optimizes the evidence lower bound (ELBO), reconstruction accuracy minus a KL-divergence term that pulls the encoder's output distribution toward N(0, I), which is what keeps the latent space smooth and usable for sampling.
---
## Answer
Separately from how sampling is made differentiable, the VAE's training objective itself has two competing terms. The reconstruction term measures how well the decoder can rebuild the input from a sampled latent code, the same kind of loss an ordinary autoencoder would use. The second term is a KL divergence between the encoder's predicted distribution q(z|x) and a fixed prior, typically the standard normal N(0, I), and it's subtracted from the reconstruction score to form the evidence lower bound (ELBO) that training maximizes.

Without the KL term, the encoder is free to spread encodings arbitrarily far apart in latent space with tiny variances, effectively memorizing inputs like a regular autoencoder, since there's nothing pulling different encodings toward a shared, sample-able region. The KL penalty forces every input's encoding to stay close to the same N(0, I) prior, which is what makes it possible to later draw a random z from that prior and decode it into a plausible, novel output, rather than something the model has only ever seen encoded from real inputs.
