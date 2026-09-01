---
uuid: sib-paper-gan-wgan
title: Mode collapse - why vanilla GANs converge to low output diversity
summary: A generator trained against JS divergence has no penalty for ignoring parts of the real data distribution, so it can minimize its loss by producing only a small subset of plausible outputs; this collapse is the core training pathology Wasserstein-style objectives were designed to reduce.
---
## Answer
A GAN generator only needs to fool the discriminator on the samples it actually produces - nothing in the standard minimax objective rewards covering the full diversity of the real data distribution. If producing a handful of highly convincing samples reliably fools the current discriminator, the generator has no gradient pressure to produce anything else.

The result is mode collapse: the generator settles on a small, repetitive subset of outputs (in extreme cases, nearly identical images regardless of the input noise vector) even though the discriminator loss looks fine. Because JS divergence saturates once the generated and real distributions don't overlap, the generator also gets weak or zero gradient exactly when it most needs a strong training signal.

This pathology, not just training instability, is a large part of the motivation for reformulating the objective around a distance metric that stays gradient-rich and diversity-sensitive throughout training.
