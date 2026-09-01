---
uuid: paper-rms-definition
title: RMSNorm: layer norm without the mean-centering step
summary: Only the root-mean-square scaling is applied; no mean subtraction; saves compute; matches LayerNorm quality on most transformer tasks.
status: active
tags: [rmsnorm, normalization, transformer]
source: https://arxiv.org/abs/1910.07467
---
## Answer
RMSNorm:
```
rms = sqrt(mean(x^2) + eps)
x_hat = x / rms
y = gamma * x_hat
```

No mean subtraction, no learned beta. Empirically matches LayerNorm on most transformer benchmarks with ~10-15% less compute.

Used in LLaMA, Gemma, and most modern open-weight LLMs.
