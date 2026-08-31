---
uuid: paper-w2v-dim
title: Word2Vec: embedding dimension is a hyperparameter; typical values 50–300
summary: Paper used 300 for the 6B token Google News model; smaller dim (50-100) is often enough for downstream tasks and trains faster.
status: active
tags: [word2vec, dimension]
source: https://arxiv.org/abs/1301.3781
---
## Answer
Embedding dimension d is a free hyperparameter.

Original paper used d=300 for the 6B token Google News model.
Smaller d (50-100) often works fine for downstream tasks and trains ~3x faster.

## Don't
Don't assume larger is always better — overfitting becomes a problem at small corpus sizes.
