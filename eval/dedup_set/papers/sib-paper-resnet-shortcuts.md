---
uuid: sib-paper-resnet-shortcuts
title: Plain deep nets get WORSE training error as depth increases, ruling out overfitting
summary: The degradation problem motivating ResNet is that stacking more layers onto a plain (non-residual) network raises training error, not just test error, so it can't be explained by overfitting - deeper plain nets are strictly harder to optimize.
---
## Answer
Before proposing shortcut connections, the ResNet paper establishes the problem they solve. Adding more layers to a conventional, non-residual network should never hurt training accuracy in principle: a deeper network can always represent its shallower counterpart by setting extra layers to the identity function. In practice, the paper shows the opposite happens. Plain networks with more layers exhibit higher training error than their shallower versions, not just higher test error.

Because the gap shows up on the training set itself, overfitting cannot be the explanation, an overfit model would have low training error and high test error. The real cause is optimization difficulty: very deep plain networks become hard to train with standard gradient descent, apparently because the layers struggle to learn even a near-identity mapping when needed. This "degradation problem," not a capacity limit, is what residual connections are designed to fix.
