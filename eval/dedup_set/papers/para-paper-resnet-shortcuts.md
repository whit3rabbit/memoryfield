---
uuid: para-paper-resnet-shortcuts
title: ResNet shortcuts are plain addition when shapes match, a 1x1 conv when they don't
summary: A skip connection adds the block's input straight to its output when the channel count and spatial size are unchanged, and routes the input through a learned 1x1 convolution first when a stride-2 downsample or channel change breaks that match.
---
## Answer
There are two flavors of shortcut in a residual block. The plain one is `y = F(x) + x`: the input is added directly to the residual branch's output, requiring no extra parameters, and only works when `x` and `F(x)` already have matching shape. The second flavor, `y = F(x) + W_s x`, inserts a learned 1x1 convolution `W_s` on the skip path so its output shape matches `F(x)` even after a stride-2 downsampling layer or a change in channel count.

In practice the paper finds the plain identity version does almost all the work: swapping in projection shortcuts everywhere yields only a marginal accuracy gain over using them solely at the dimension-change points, at the cost of noticeably more parameters.
