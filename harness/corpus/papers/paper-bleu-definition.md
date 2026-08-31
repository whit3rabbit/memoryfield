---
uuid: paper-bleu-definition
title: BLEU score: n-gram overlap between candidate and reference translations
summary: BLEU = BP * exp(sum w_n log p_n); p_n = modified n-gram precision; BP = brevity penalty; range 0-100; standard metric for translation.
status: active
tags: [bleu, evaluation, translation]
source: https://aclanthology.org/P02-1040/
---
## Answer
BLEU (Papineni et al., 2002):

```
BLEU = BP * exp(sum_{n=1..4} w_n * log p_n)
```

- `p_n` = modified n-gram precision: count of n-grams in candidate that appear in any reference, clipped by max count in any reference.
- `BP` = brevity penalty: `exp(1 - r/c)` if candidate shorter than reference, else 1.
- Weights default: uniform (0.25 each).

Range 0-100. Higher is better. > 30 is decent; > 50 is good human-translation territory.
