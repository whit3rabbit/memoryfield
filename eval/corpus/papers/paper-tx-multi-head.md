---
uuid: paper-tx-multi-head
title: "Transformer: multi-head attention lets the model attend to different representation subspaces"
summary: "h parallel attention heads run in parallel; outputs are concatenated and projected; 8 heads in the base model."
status: active
tags: [transformer, multi-head]
source: "https://arxiv.org/abs/1706.03762"
---
## Answer
`MultiHead(Q,K,V) = Concat(head_1,...,head_h) W^O`
where `head_i = Attention(QW_i^Q, KW_i^K, VW_i^V)`.

The base model uses h=8. This lets each head attend to a different representation subspace.
