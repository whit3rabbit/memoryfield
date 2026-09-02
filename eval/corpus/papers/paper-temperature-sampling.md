---
uuid: paper-temperature-sampling
title: "Temperature in sampling: T<1 sharpens; T>1 flattens"
summary: "softmax(logits/T); T=1 is the model's natural distribution; T=0 is argmax (greedy); T>1 is more random; lower T produces more deterministic outputs."
status: active
tags: [sampling, temperature, decoding]
source: "https://arxiv.org/abs/1904.09751"
---
## Answer
Sampling temperature T:
- T = 0: argmax (greedy decoding, fully deterministic).
- T < 1: sharper distribution (peaks amplified). Use for factual / code.
- T = 1: model's natural distribution.
- T > 1: flatter distribution (more random). Use for creative writing.

Practical range: 0.1 to 1.5 for most tasks. T = 0.7 is a common default for chat.
