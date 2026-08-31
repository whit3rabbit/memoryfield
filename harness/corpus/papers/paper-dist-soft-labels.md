---
uuid: paper-dist-soft-labels
title: Knowledge distillation: train a small model to match a large model's soft outputs
summary: Student is trained on a softmax of the teacher's logits at temperature T > 1; the soft labels carry more information than hard labels.
status: active
tags: [distillation, training, compression]
source: https://arxiv.org/abs/1503.02531
---
## Answer
Distillation loss:
```
L = alpha * L_hard(student, true_labels) + (1 - alpha) * L_soft(student, teacher)
```
where `L_soft` uses softmax with temperature `T > 1` (typically T=2-5).

Higher T produces softer probability distributions, which encode inter-class similarities that hard labels miss (e.g., 'this image is 0.7 truck, 0.3 car' rather than just 'truck').
