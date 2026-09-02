---
uuid: paper-ln-vs-bn
title: "LayerNorm vs BatchNorm: which to use when"
summary: "BatchNorm: CNNs, fixed batch sizes, faster training. LayerNorm: transformers, RNNs, variable batch sizes, distributed training."
status: active
tags: [layernorm, batchnorm, comparison]
source: "https://arxiv.org/abs/1607.06450"
---
## Answer
Rule of thumb:
- **BatchNorm**: convolutional networks with large fixed batch sizes; benefits from batch noise as regularization.
- **LayerNorm**: transformers (BERT, GPT, etc.), RNNs, anywhere batch statistics are awkward or vary.

Most NLP models use LayerNorm exclusively. Most vision CNNs (without transformers) use BatchNorm.

## Don't
Don't mix BatchNorm and LayerNorm in the same model without thinking it through -- they interact with optimizer settings differently.
