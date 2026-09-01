---
uuid: paper-ppo-default
title: PPO: the de facto RL algorithm for continuous and discrete control tasks
summary: First-choice algorithm for most RLHF, robotics, and game-playing setups; robust across hyperparameter settings; easy to implement.
status: active
tags: [ppo, rl, default]
source: https://arxiv.org/abs/1707.06347
---
## Answer
PPO is widely treated as the default policy-gradient algorithm:
- Robust across hyperparameters (compared to A2C, TRPO).
- Implementable in ~100 lines (compared to TRPO's constrained optimization).
- Works on continuous and discrete action spaces.

Used in: RLHF (InstructGPT, early ChatGPT), robotics (OpenAI's Dactyl), game AI (Dota 2 Five).
