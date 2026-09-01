---
uuid: para-paper-cosine-similarity
title: Cosine similarity measures vector direction, not length
summary: Defined as the dot product of two vectors divided by the product of their magnitudes, cosine similarity ranges from -1 to 1 and is the default way to compare embeddings since it ignores vector scale.
---
## Answer
Cosine similarity between two vectors A and B is `(A . B) / (|A| * |B|)` - the dot product normalized by both magnitudes, which is mathematically the cosine of the angle between them.

Range and meaning: 1 means the vectors point in the exact same direction (maximally similar), 0 means they're orthogonal (unrelated), -1 means they point in opposite directions. Because the magnitudes are divided out, only direction matters - two vectors that point the same way but differ in length still score 1.

This scale-invariance is why it's the default similarity for word embeddings, sentence embeddings, and dense retrieval generally. One optimization worth knowing: if vectors are already unit-normalized ahead of time, cosine similarity reduces to a plain dot product, which is considerably cheaper to compute at scale.
