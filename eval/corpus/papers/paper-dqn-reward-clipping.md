---
uuid: paper-dqn-reward-clipping
title: "DQN: rewards clipped to {-1, 0, +1} to handle different game score scales"
summary: "Sign of reward, not magnitude; allows one set of hyperparameters to work across games with wildly different raw scores (Pong: +/-1; Ms. Pac-Man: thousands)."
status: active
tags: [dqn, reward-clipping]
source: "https://www.nature.com/articles/nature14236"
---
## Answer
Reward clipping: positive reward becomes +1, negative becomes -1, zero stays 0.

This normalizes the reward scale across games. Without clipping, gradient magnitudes would vary wildly between games (e.g., Pong: +/-1 reward vs. Ms. Pac-Man: thousands).

This is one of the tricks that makes the cross-game single-hyperparameter setup work.
