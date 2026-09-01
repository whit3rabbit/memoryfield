---
uuid: para-paper-tfidf-definition
title: TF-IDF weighs a term by how often it appears here versus how rare it is overall
summary: Multiply a term's within-document frequency by the log of the corpus size divided by how many documents contain that term, so common-but-distinctive words score highest and words appearing everywhere score near zero.
---
## Answer
TF-IDF scores are built from two opposing signals about a term t in a document d. Term frequency rewards words that show up often within d, on the theory that repetition signals topical importance. Inverse document frequency penalizes words that show up in many documents across the whole corpus, on the theory that a word everyone uses (like "the" or, in a technical corpus, a domain-generic word) carries little discriminating power.

The standard formula multiplies the two: tfidf(t, d) = tf(t, d) * log(N / df(t)), where N is the total document count and df(t) is how many documents contain t. For decades this was the default way to score document relevance for a query. Dense embedding retrievers have since overtaken it on most benchmarks, though TF-IDF remains hard to beat for exact-match and code search, where surface-form overlap is itself the useful signal.
