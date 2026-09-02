---
uuid: paper-cosine-similarity
title: "Cosine similarity: angle between two vectors, ignoring magnitude"
summary: "cos(theta) = (A . B) / (|A| * |B|); range -1 to 1; standard similarity for normalized embeddings; high = similar direction in vector space."
status: active
tags: [similarity, embeddings]
source: "https://en.wikipedia.org/wiki/Cosine_similarity"
---
## Answer
Cosine similarity = cosine of the angle between two vectors.

`cos(theta) = (A . B) / (|A| * |B|)`

Properties:
- Range -1 to 1 (1 for normalized vectors, 0 for orthogonal, -1 for opposite).
- Scale-invariant (only direction matters).
- The standard similarity for word embeddings, sentence embeddings, and dense retrieval.

When vectors are pre-normalized, similarity = dot product -- much faster.
