---
uuid: paper-tx-positional
title: "Transformer: positional encoding uses sinusoids"
summary: "PE(pos, 2i) = sin(pos / 10000^(2i/d_model)); PE(pos, 2i+1) = cos(...); allows the model to extrapolate to sequence lengths beyond training."
status: active
tags: [transformer, positional-encoding]
source: "https://arxiv.org/abs/1706.03762"
---
## Answer
Sinusoidal positional encodings:
```
PE(pos, 2i) = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
```
The authors hypothesized this would help with extrapolation to longer sequences (a property later shown to be weaker than hoped).
