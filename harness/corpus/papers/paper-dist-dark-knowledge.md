---
uuid: paper-dist-dark-knowledge
title: Distillation: why soft labels encode more than hard labels
summary: A 0.7 truck / 0.3 car distribution encodes similarity to other classes; a 1.0 truck hard label doesn't; the student learns relationships, not just categories.
status: active
tags: [distillation, theory]
source: https://arxiv.org/abs/1503.02531
---
## Answer
Hinton et al.'s 'dark knowledge' insight: the teacher's soft probability distribution encodes inter-class similarities that hard labels miss.

Example: a car and a truck share visual features. Hard labels say 'truck' (1.0, 0.0). Soft labels say 'truck 0.7, car 0.2, vehicle 0.1'. The student learns 'trucks look like cars' from the second case, not the first.

This is why distillation can outperform training on the original labels.
