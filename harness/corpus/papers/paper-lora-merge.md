---
uuid: paper-lora-merge
title: LoRA: adapters can be merged into the base model for zero-latency inference
summary: After training, `W_new = W_0 + B@A`; merged once into the model weights; inference has no adapter overhead.
status: active
tags: [lora, inference]
source: https://arxiv.org/abs/2106.09685
---
## Answer
After training, the merge is:
```python
W_0.data += B @ A
```

This produces a model with the LoRA adaptation baked in — same forward-pass latency and memory as the base model.

## Don't
Don't keep adapters separate at inference time if you can merge them. Merging saves the dispatch overhead.
