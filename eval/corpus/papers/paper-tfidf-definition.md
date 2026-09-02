---
uuid: paper-tfidf-definition
title: "TF-IDF: term frequency times inverse document frequency"
summary: "TF(t,d) * IDF(t) = count(t in d) / |d| * log(N / df(t)); rewards words common in a document but rare in the corpus; classic IR baseline before dense retrievers."
status: active
tags: [tfidf, ir, lexical]
source: "https://en.wikipedia.org/wiki/Tf%E2%80%93idf"
---
## Answer
TF-IDF combines two intuitions:
- **TF (term frequency)**: words that appear a lot in a document are likely important.
- **IDF (inverse document frequency)**: words that appear in many documents are less discriminative.

Common formulation:
`tfidf(t, d) = tf(t, d) * log(N / df(t))`

Was the standard retrieval baseline for decades. Now dominated by dense retrievers but still competitive for code and exact-match recall.
