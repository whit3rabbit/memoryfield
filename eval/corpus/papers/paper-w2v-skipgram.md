---
uuid: paper-w2v-skipgram
title: Word2Vec: skip-gram predicts context words from a center word
summary: Given a center word, predict context words within a window; negative sampling uses ~5-20 noise words instead of full softmax for efficiency.
status: active
tags: [word2vec, embedding, training]
source: https://arxiv.org/abs/1301.3781
---
## Answer
Skip-gram with negative sampling (SGNS):
- Slide a window over the corpus.
- For each (center, context) pair, train the model to predict `context` from `center`.
- Use negative sampling: for each positive pair, draw k=5–20 random "noise" words and train the model to score them lower.

Negative sampling turns the softmax into a binary classification problem, which is ~1000x faster.
