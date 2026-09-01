---
uuid: sib-paper-cosine-similarity
title: Pre-normalizing embeddings lets ANN indexes use inner product instead of cosine
summary: Approximate nearest neighbor libraries (FAISS, HNSW) are often faster with a raw inner-product metric than a true cosine metric; L2-normalizing vectors at index-build time makes inner product and cosine ranking identical, avoiding a per-comparison division.
---
## Answer
Cosine similarity requires dividing by both vector magnitudes on every comparison, which is extra work an ANN index has to redo for every candidate during search. Most ANN libraries (FAISS, HNSW-based indexes) offer a raw inner-product metric that skips that division.

The trick: if every vector is L2-normalized to unit length before insertion, its magnitude is always 1, so the division term in the cosine formula becomes a no-op. Inner product on unit vectors then produces exactly the same ranking as cosine similarity would.

Practical upshot: normalize embeddings once at write time (not at query time, and not repeatedly), then build the index with an inner-product or dot-product metric rather than a cosine metric - the search itself gets measurably faster with no ranking difference, since the normalization did the work up front.
