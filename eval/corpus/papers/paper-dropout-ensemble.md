---
uuid: paper-dropout-ensemble
title: "Dropout: acts as an ensemble of exponentially many thinned networks"
summary: "Each training pass uses a different sub-network of the original; at test time the full network approximates the ensemble's predictions."
status: active
tags: [dropout, theory]
source: "https://www.jmlr.org/papers/v15/srivastava14a.html"
---
## Answer
With n units and dropout probability p, each forward pass uses one of `2^n` possible sub-networks.

Srivastava et al. argue this is similar to model averaging / ensemble: training on 2^n thinned networks and using the full network at test time approximates the geometric mean of predictions across the ensemble.
