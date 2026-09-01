---
uuid: para-paper-dqn-atari-results
title: DQN beat human-level play on 43 of 49 Atari titles
summary: Using one fixed architecture and hyperparameter set across all 49 games, tested purely from raw pixels, DQN surpassed expert human scores on 43 of them; the six failures include the well-known Montezuma's Revenge case.
---
## Answer
The DQN evaluation ran the Arcade Learning Environment's 49 Atari 2600 titles through a single network architecture with a single set of hyperparameters - no per-game tuning. Input was raw pixel frames plus the in-game score, nothing hand-engineered.

The headline result: 43 of the 49 games ended with DQN scoring above an expert human baseline. The remaining 6 games were not solved to that bar, and the most cited failure among them is Montezuma's Revenge, which requires long-horizon exploration the algorithm couldn't manage.

What made this notable at the time wasn't any single game's score - it was that one unmodified architecture generalized across 49 structurally different games, which was unusual for reinforcement learning up to that point.
