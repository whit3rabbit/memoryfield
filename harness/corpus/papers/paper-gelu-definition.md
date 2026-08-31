---
uuid: paper-gelu-definition
title: GELU: Gaussian Error Linear Unit activation used in transformers
summary: GELU(x) = x * Phi(x) where Phi is the standard normal CDF; smooth approximation of ReLU with non-zero gradient everywhere.
status: active
tags: [gelu, activation, transformer]
source: https://arxiv.org/abs/1606.08415
---
## Answer
GELU(x) = x * Phi(x), where Phi is the standard normal CDF.

Equivalent forms:
- 0.5 * x * (1 + erf(x / sqrt(2)))
- 0.5x(1 + tanh(sqrt(2/pi) * (x + 0.044715 x^3))) (approximation)

Used in BERT, GPT, RoBERTa, and most modern transformers. Smoother than ReLU (non-zero gradient for negative inputs) which empirically helps optimization.
