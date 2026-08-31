---
uuid: paper-why-dropping-mean-centering-works
title: RMSNorm: why dropping mean-centering works
summary: The re-centering operation has minimal effect because the subsequent linear layer can absorb any constant offset; the re-scaling is what actually stabilizes training.
status: active
tags: [rmsnorm, theory]
source: https://arxiv.org/abs/1910.07467
---
## Answer
LayerNorm's re-centering step shifts activations to zero mean. But:
- The next linear layer (y = Wx + b) absorbs any constant offset via its bias b.
- The re-scaling (dividing by std) is what stabilizes training by controlling activation magnitudes.

Empirically, dropping the mean subtraction loses ~0% accuracy on most benchmarks while saving compute. The paper argues the rescaling is the load-bearing part.
