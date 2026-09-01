---
uuid: paper-mamba-arch
title: Mamba: selective state-space model that competes with transformers
summary: Replaces attention with a selective state-space layer; input-dependent discretization of a continuous-time linear recurrence; linear-time inference; competitive with transformers on language.
status: active
tags: [mamba, ssm, architecture]
source: https://arxiv.org/abs/2312.00752
---
## Answer
Mamba is a selective state-space model:
- Continuous-time linear recurrence: `h'(t) = A h(t) + B x(t)`, `y(t) = C h(t)`.
- Discretized per-step with input-dependent `A`, `B`, `C` (the 'selective' part).
- Linear-time inference (no quadratic attention).
- Trained with a hardware-aware parallel scan.

Competitive with similarly-sized transformers on language modeling and several downstream tasks. The hybrid Mamba+attention (Jamba) is the production form.
