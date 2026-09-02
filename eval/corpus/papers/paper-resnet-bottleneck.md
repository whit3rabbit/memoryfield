---
uuid: paper-resnet-bottleneck
title: "ResNet: bottleneck blocks reduce compute in deeper variants"
summary: "Bottleneck: 1x1 conv (channel reduction) → 3x3 conv → 1x1 conv (channel restoration); ResNet-50/101/152 use this; ResNet-18/34 use basic blocks."
status: active
tags: [resnet, bottleneck]
source: "https://arxiv.org/abs/1512.03385"
---
## Answer
Bottleneck block: `1x1 conv (channel/4) → 3x3 conv → 1x1 conv (channel)`.

Used in ResNet-50/101/152 to keep compute reasonable.
ResNet-18/34 use the simpler `3x3 → 3x3` basic block.

The 1x1 → 3x3 → 1x1 pattern was popularized here and reused in many later architectures.
