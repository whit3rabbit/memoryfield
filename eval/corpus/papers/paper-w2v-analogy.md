---
uuid: paper-w2v-analogy
title: "Word2Vec: classic analogy example `king - man + woman ≈ queen`"
summary: "Linear algebra on embeddings reproduces semantic relationships; the famous example comes from the original paper and the subsequent tooling."
status: active
tags: [word2vec, analogy]
source: "https://arxiv.org/abs/1301.3781"
---
## Answer
`vec(king) - vec(man) + vec(woman) ≈ vec(queen)`

This works for many semantic relationships (gender, country-capital, verb tense) but not all — and the effect degrades for rare words.

It is the iconic demonstration that word embeddings encode linear structure.
