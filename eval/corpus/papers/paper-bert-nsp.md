---
uuid: paper-bert-nsp
title: BERT: next sentence prediction (NSP) was later shown to be mostly useless
summary: NSP head contributed little to downstream performance; subsequent work (RoBERTa, ALBERT) dropped it with no loss.
status: active
tags: [bert, nsp, design-choice]
source: https://arxiv.org/abs/1810.04805
---
## Answer
NSP was a 50/50 binary classification task predicting whether sentence B follows sentence A in the corpus.

Subsequent work (RoBERTa, 2019) showed NSP contributes little; removing it doesn't hurt and sometimes helps. ALBERT went further with sentence-order prediction (SOP).

## Don't
Don't cite BERT's NSP results as load-bearing — the field moved on.
