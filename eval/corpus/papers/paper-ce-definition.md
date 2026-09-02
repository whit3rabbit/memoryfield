---
uuid: paper-ce-definition
title: "Cross-entropy loss: negative log-likelihood of the true class"
summary: "L = -log(p_true); for one-hot y: L = -sum y_i log(p_i); combined with softmax gives a clean gradient equal to (p - y)."
status: active
tags: [cross-entropy, loss, fundamentals]
source: "https://en.wikipedia.org/wiki/Cross-entropy"
---
## Answer
Cross-entropy loss:
`L = -sum_i y_i * log(p_i)`

For one-hot labels where y_k = 1, this simplifies to:
`L = -log(p_k)`

When combined with softmax as the output activation, the gradient is `p - y` -- the cleanest possible gradient for classification. This is why softmax + cross-entropy is the standard pair.
