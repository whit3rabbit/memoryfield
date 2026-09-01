---
uuid: sib-paper-softmax-definition
title: Softmax temperature controls how peaked or flat the output distribution is
summary: Dividing logits by a temperature T before applying softmax - softmax(x_i/T) - sharpens the distribution toward one-hot as T shrinks below 1 and flattens it toward uniform as T grows above 1, independent of the base softmax formula itself.
---
## Answer
Temperature is a scalar applied before the softmax function, not a change to softmax's own formula. Given logits x and temperature T, the computation becomes softmax(x/T) = exp(x_i/T) / sum_j exp(x_j/T).

As T approaches 0, dividing by a small number stretches the logit gaps enormously, so the largest logit dominates and the output approaches a one-hot vector (equivalent to argmax). As T grows large, dividing shrinks the gaps toward zero, so all exponentials converge to similar values and the output approaches a uniform distribution over all classes.

This is the standard knob for controlling sampling diversity in language model generation: low temperature for deterministic, high-confidence output; high temperature for more varied, exploratory output. It composes with truncation methods like top-k or top-p, which are applied to the temperature-adjusted distribution.
