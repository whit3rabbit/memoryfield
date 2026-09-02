---
uuid: paper-lora-rank
title: "LoRA: rank r=8 captures most of the fine-tuning quality"
summary: "Empirically, r=4-16 is enough for most tasks; very large r doesn't help much but does increase parameter count."
status: active
tags: [lora, rank, hyperparameter]
source: "https://arxiv.org/abs/2106.09685"
---
## Answer
The original paper shows that rank 4-16 captures most of the fine-tuning quality for tasks like WikiSQL and MNLI-matched.

Rank 64+ gives diminishing returns. Going higher than 64 essentially defeats the purpose.

## Don't
Don't blindly use r=64 — start at r=8, increase only if quality is insufficient.
