---
uuid: sib-paper-nucleus-sampling
title: Nucleus sampling was proposed because greedy and beam search degenerate into repetition
summary: Maximum-likelihood decoding (greedy or beam search) produces bland, loopy, repetitive text because the highest-probability continuation under a trained LM diverges from what humans actually write - sampling-based decoding fixes this, not decoding accuracy.
---
## Answer
The nucleus sampling paper's motivating observation isn't about how to pick a token set, it's about why picking the single most likely continuation at every step goes wrong. Greedy decoding and even wide beam search on neural language models tend to fall into repetitive loops ("I don't know. I don't know. I don't know.") or generic, low-information text.

The authors show this is a structural mismatch: human-written text does not consist of the locally highest-probability word at each position, it has natural variance. Maximizing likelihood at generation time therefore produces text that is statistically unlike the training distribution, even though the model itself fits that distribution well. This is the argument for sampling-based decoding methods generally, independent of which truncation rule (top-k, top-p) is used to keep sampling from picking implausible tokens.
