---
uuid: paper-bert-mlm
title: "BERT: bidirectional pretraining via masked language modeling"
summary: "15% of tokens are masked; of those, 80% become [MASK], 10% random token, 10% unchanged; the model predicts the original."
status: active
tags: [bert, mlm, pretraining]
source: "https://arxiv.org/abs/1810.04805"
---
## Answer
Masked Language Modeling (MLM) with a 15% mask rate. Of the masked tokens:
- 80% → [MASK]
- 10% → random token
- 10% → unchanged

The random/unchanged fractions prevent the model from learning that masked tokens always map to [MASK] at fine-tuning.
