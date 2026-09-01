---
uuid: sib-paper-tfidf-definition
title: Smoothed IDF adds 1 to the document count to avoid a divide-by-zero on unseen terms
summary: Plain IDF (log(N/df(t))) breaks down or spikes unpredictably when df(t) is 0 or 1, so production TF-IDF implementations commonly use log(N / (1 + df(t))) + 1 or similar smoothing so every term gets a finite, bounded weight.
---
## Answer
The textbook IDF formula log(N / df(t)) has an edge case its simplicity hides: if a term never appears in the corpus used to fit the vectorizer, df(t) is 0 and the ratio is undefined. Even for terms that appear in exactly one document, IDF spikes to its maximum possible value, which can let a single rare, possibly noisy token dominate a similarity score.

Practical implementations, including scikit-learn's default, use a smoothed variant: add 1 to both N and every df(t) before taking the log, then add 1 to the result, effectively treating every term as if it appeared in one additional "phantom" document. This keeps the weight finite for zero-count terms and pulls in the extreme values for rare terms, trading a small amount of theoretical purity for numerical stability and less sensitivity to corpus size.
