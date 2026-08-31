---
uuid: paper-vae-elbo
title: VAE: ELBO is the lower bound on log-likelihood being maximized
summary: ELBO = E_q[log p(x|z)] - KL(q(z|x) || p(z)); equivalent to the loss written as reconstruction + KL; the bound is tight when q matches p(z|x).
status: active
tags: [vae, elbo, theory]
source: https://arxiv.org/abs/1312.6114
---
## Answer
ELBO (Evidence Lower Bound):
`log p(x) >= E_q(z|x)[log p(x|z)] - KL(q(z|x) || p(z))`

The training loss is `-ELBO`. Maximizing ELBO maximizes a lower bound on the true log-likelihood. The bound is tight when `q(z|x) = p(z|x)` exactly.
