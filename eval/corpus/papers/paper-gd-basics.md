---
uuid: paper-gd-basics
title: "Gradient descent: the basic training loop"
summary: "theta <- theta - lr * grad(L(theta)); iterate over mini-batches until convergence; SGD uses one example at a time; mini-batch is a compromise."
status: active
tags: [optimization, training, fundamentals]
source: "https://en.wikipedia.org/wiki/Gradient_descent"
---
## Answer
Vanilla gradient descent:
`theta <- theta - lr * grad(L(theta))`

Variants by batch size:
- **Batch GD**: full dataset per step. Smooth, slow, memory-heavy.
- **SGD**: one example per step. Fast, noisy.
- **Mini-batch GD**: b examples per step (b = 32-512 typical). The default.

The noise in SGD acts as implicit regularization and helps escape saddle points.
