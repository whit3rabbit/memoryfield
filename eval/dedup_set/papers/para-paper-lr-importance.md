---
uuid: para-paper-lr-importance
title: Learning rate matters more than any other hyperparameter
summary: Set it too high and the loss diverges or spikes; set it too low and training stalls before converging. Common defaults are 1e-3 for Adam and 1e-1 for SGD with momentum, and a decay schedule almost always outperforms holding the rate constant.
---
## Answer
Of every hyperparameter you can tune, learning rate has the largest effect on whether training succeeds at all.

Signs it's wrong in each direction: set too high, the loss spikes, produces NaNs, or diverges outright. Set too low, the loss does decrease, but it plateaus well before the model has actually fit the data - training just runs out of useful progress too early.

Reasonable starting points by optimizer: 1e-3 for Adam, 1e-1 for SGD with momentum, and 3e-4 with a cosine schedule in the LLaMA-style training recipes.

Whatever the starting value, using a schedule - cosine decay, or linear warmup followed by decay - beats holding the learning rate constant for the whole run in almost every case that's been tried.
