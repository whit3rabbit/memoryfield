---
uuid: paper-lora-decomposition
title: LoRA: low-rank decomposition of weight updates freezes W, trains A and B
summary: ΔW = BA where B ∈ R^(d×r), A ∈ R^(r×k), r << min(d,k); only A and B are trained; the original W is frozen and merged back at inference.
status: active
tags: [lora, peft, training]
source: https://arxiv.org/abs/2106.09685
---
## Answer
For a pretrained weight matrix `W_0 ∈ R^(d×k)`, LoRA constrains the update to:
`W = W_0 + ΔW = W_0 + (B @ A)` where `B ∈ R^(d×r)`, `A ∈ R^(r×k)`, `r << min(d,k)`.

Only A and B receive gradients. At inference, `W = W_0 + B@A` is computed once and merged back into the original matrix — no latency overhead.

Typical `r` values: 4, 8, 16, 32.
