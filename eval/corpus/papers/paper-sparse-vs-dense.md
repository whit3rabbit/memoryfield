---
uuid: paper-sparse-vs-dense
title: "Sparse vs dense retrieval: when each wins"
summary: "Sparse (BM25, TF-IDF): exact term matches, fast, predictable. Dense (embeddings): semantic similarity, robust to vocabulary mismatch. Hybrid fuses both."
status: active
tags: [retrieval, comparison]
source: "https://en.wikipedia.org/wiki/Sparse_retrieval"
---
## Answer
Tradeoffs:

**Sparse** (BM25, TF-IDF):
- Wins on exact term matches (code, error strings, proper nouns).
- Fast, no model serving.
- Fails on vocabulary mismatch ("JWT" vs "auth token").

**Dense** (embeddings):
- Wins on semantic similarity.
- Robust to paraphrase.
- Fails on exact-match recall (rare terms, code symbols).

Hybrid (RRF fusion of both) is the production default.
