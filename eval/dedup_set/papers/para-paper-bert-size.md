---
uuid: para-paper-bert-size
title: BERT-base and BERT-large parameter counts
summary: BERT-base uses 12 layers, 768 hidden size, 12 heads for 110M parameters; BERT-large scales to 24 layers, 1024 hidden, 16 heads for 340M parameters.
---
## Answer
Devlin et al.'s original BERT release shipped two configurations. The smaller, BERT-base, stacks 12 transformer layers with hidden dimension 768 and 12 attention heads, landing at 110M total parameters.

The larger, BERT-large, roughly doubles depth and widens the hidden dimension: 24 layers, hidden size 1024, 16 attention heads, for 340M parameters total.

These two configurations became reference points for the field - later architectures like RoBERTa, DistilBERT, and ALBERT are typically described as scaled or compressed variants of one or the other rather than defining entirely new size classes.
