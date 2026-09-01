---
uuid: para-paper-softmax-definition
title: Softmax converts a vector of scores into a normalized probability distribution
summary: Each exponentiated score is divided by the sum of all exponentiated scores, guaranteeing non-negative outputs that sum to 1; the max-subtraction trick keeps the exponentials from overflowing on large logits.
---
## Answer
Given raw scores x_1..x_n, softmax computes exp(x_i) / sum_j exp(x_j) for each entry. Exponentiating first means every output is positive, and dividing by the total means all outputs add up to exactly 1, so the result can be read as a probability distribution over classes.

Because exponentials grow fast, softmax also exaggerates gaps between scores, a small lead in the raw logits becomes a much larger lead in probability space. This is why it's the standard choice for classifier output layers and for turning attention scores into weights.

One implementation detail matters for large logit values: computing exp(x_i) directly can overflow. The fix is to subtract the max logit from every entry before exponentiating, which leaves the final probabilities unchanged but keeps every exponent bounded.
