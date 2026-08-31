---
uuid: paper-perplexity-definition
title: Perplexity: exponentiated cross-entropy of a probability distribution
summary: PPL = exp(-1/N * sum log p(x_i)); lower is better; standard evaluation for language models; 20-50 for well-trained small LMs, lower for larger.
status: active
tags: [perplexity, evaluation, lm]
source: https://en.wikipedia.org/wiki/Perplexity
---
## Answer
Perplexity = exp(cross-entropy) = exp(-1/N * sum log p(x_i))

Interpretation: the effective branching factor the model considers at each step.
- PPL = 1: model assigns probability 1 to every correct token.
- PPL = V (vocab size): uniform distribution.
- PPL = 20-50: well-trained small LM.
- PPL < 10: strong modern LM.

Larger models generally achieve lower PPL on the same corpus.
