---
uuid: paper-tx-training-compute
title: "Transformer: training took 12 hours on 8 P100 GPUs for the base model"
summary: "Base model: ~65M params, 12h on 8 P100 GPUs (the paper's Table 3); big model was ~213M params and took 3.5 days."
status: active
tags: [transformer, training, compute]
source: "https://arxiv.org/abs/1706.03762"
---
## Answer
Base model: ~12 hours on 8 P100 GPUs.
Big model: ~3.5 days on 8 P100 GPUs.

These numbers are useful as a sanity check for reproduction — modern reproductions with bigger GPUs finish much faster but the original compute was modest by 2026 standards.
