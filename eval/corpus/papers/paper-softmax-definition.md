---
uuid: paper-softmax-definition
title: Softmax: turns logits into a probability distribution
summary: softmax(x_i) = exp(x_i) / Sigma_j exp(x_j); outputs sum to 1; amplifies differences; numerically unstable for large logits (subtract max first).
status: active
tags: [softmax, activation, fundamentals]
source: https://en.wikipedia.org/wiki/Softmax_function
---
## Answer
softmax(x_i) = exp(x_i) / sum_j exp(x_j)

Properties:
- Outputs are non-negative and sum to 1 (a probability distribution).
- Amplifies differences: large logit differences become near-binary probabilities.
- Used for multi-class classification output layers and attention weights.

Numerical stability: subtract max before exp to avoid overflow:
`softmax(x) = exp(x - max(x)) / sum exp(x - max(x))`
