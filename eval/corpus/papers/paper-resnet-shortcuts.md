---
uuid: paper-resnet-shortcuts
title: "ResNet: shortcut connections can be identity or projection"
summary: "Identity shortcuts when dimensions match; projection shortcuts (1x1 conv) when dimensions change; identity works in practice for most layers."
status: active
tags: [resnet, architecture]
source: "https://arxiv.org/abs/1512.03385"
---
## Answer
Two shortcut types:
- **Identity shortcut**: `y = F(x) + x`. Used when `F`'s output has the same dimensions as `x`.
- **Projection shortcut**: `y = F(x) + W_s x` where `W_s` is a 1x1 conv. Used when dimensions change (stride 2 downsampling).

The paper notes identity shortcuts are sufficient in practice for most layers; projection shortcuts add parameters without much accuracy gain.
