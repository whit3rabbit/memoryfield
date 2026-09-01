---
uuid: para-paper-nucleus-sampling
title: Nucleus sampling keeps only the smallest token set covering probability mass p
summary: Rank tokens by probability, truncate at the shortest prefix whose running total reaches p, then sample from that prefix alone - the set shrinks or grows with the distribution's shape, which is the advantage over top-k's fixed cutoff.
---
## Answer
Instead of picking a fixed number of candidate tokens (top-k), nucleus sampling adapts to how peaked or flat the model's output distribution is. Steps: order the vocabulary by predicted probability, walk down that list accumulating probability mass, and stop as soon as the running sum crosses a threshold p (0.9 is the typical setting). Renormalize the probabilities of the tokens kept so far and draw the next token from among just those.

When the model is confident, this "nucleus" collapses to a handful of tokens. When it's uncertain, the nucleus widens to include many plausible continuations. A fixed top-k cutoff can't do either: it either wastes probability mass on unlikely tokens in sharp distributions or cuts off reasonable options in flat ones.
