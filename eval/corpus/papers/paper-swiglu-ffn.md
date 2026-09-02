---
uuid: paper-swiglu-ffn
title: "SwiGLU: gated activation in transformer FFN blocks"
summary: "FFN(x) = (W_1 x * sigma(W_gate x)) W_2; the gate controls information flow; SwiGLU uses SiLU (Swish) as the activation; outperforms ReLU/GELU FFN on most benchmarks."
status: active
tags: [swiglu, activation, transformer]
source: "https://arxiv.org/abs/2002.05202"
---
## Answer
GLU (Gated Linear Unit) FFN:
```
output = (W_1 x * sigma(W_gate x)) W_2
```

SwiGLU (Shazeer, 2020): `sigma` is SiLU/Swish (`x * sigmoid(x)`).

Standard in LLaMA, PaLM, Mistral, and most modern transformer FFNs.

A common variant: 2/3 size for `W_1` and `W_gate` to keep total parameter count constant (compensating for the extra matrix).
