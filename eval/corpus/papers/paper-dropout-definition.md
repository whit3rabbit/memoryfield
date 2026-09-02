---
uuid: paper-dropout-definition
title: "Dropout: randomly zero units during training to prevent co-adaptation"
summary: "Each forward pass zeros each unit with probability p (typically 0.5 for hidden, 0.1 for input); at test time, no dropout, weights scaled by (1-p) or invert at training."
status: active
tags: [dropout, regularization]
source: "https://www.jmlr.org/papers/v15/srivastava14a.html"
---
## Answer
During training: each unit is kept with probability `p` (commonly 0.5 for hidden layers, 0.8–0.9 for input).

During inference: all units are active, with weights scaled by `p` (or equivalently, training scales activations by `1/p` — "inverted dropout").

This prevents co-adaptation of features. Srivastava et al. show consistent gains across vision, speech, and NLP tasks.
