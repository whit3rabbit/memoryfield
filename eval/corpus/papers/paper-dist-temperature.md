---
uuid: paper-dist-temperature
title: Distillation: temperature T controls softness of probability distribution
summary: Softmax(x/T) with T=1 is the standard softmax; T>1 flattens the distribution, exposing dark knowledge; T<1 sharpens it.
status: active
tags: [distillation, temperature]
source: https://arxiv.org/abs/1503.02531
---
## Answer
Temperature scaling: `softmax(x/T)`.
- T=1: standard softmax.
- T>1: softer distribution (more uniform); reveals dark knowledge.
- T<1: sharper distribution (peaks amplified).

For distillation, T=2 to T=5 is typical. At inference, the student uses T=1.
