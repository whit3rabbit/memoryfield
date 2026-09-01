---
uuid: paper-resnet-skip
title: ResNet: residual connections let networks of 100+ layers train
summary: y = F(x) + x; the skip connection makes the residual F(x) easier to optimize than the unreferenced mapping; enabled 152-layer ImageNet models.
status: active
tags: [resnet, skip-connection, depth]
source: https://arxiv.org/abs/1512.03385
---
## Answer
Residual block: `y = F(x, {W_i}) + x`, where `F` is the convolutional stack.

The skip connection means that if the optimal transformation is the identity, the network only needs to learn `F(x) = 0` — a much easier optimization target.

This was the breakthrough that enabled training 152-layer networks (8x deeper than VGG-19) without degradation.
