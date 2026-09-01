---
uuid: para-paper-ppo-default
title: PPO became the go-to policy-gradient method across RL application areas
summary: Practitioners reach for PPO before other policy-gradient algorithms because it tolerates loose hyperparameter tuning, fits in a short implementation, and handles both discrete and continuous actions - not because it is the most sample-efficient option.
---
## Answer
Among policy-gradient algorithms, PPO occupies the "default choice" slot that TRPO and A2C don't. Two practical properties drive this: it doesn't require the constrained-optimization machinery TRPO needs (PPO can be written in roughly a hundred lines versus TRPO's more involved trust-region solve), and it stays stable across a wider range of hyperparameter choices than A2C, so less tuning effort is needed to get a working run.

It also generalizes across action spaces without modification, continuous control and discrete action problems both use the same core update. That versatility shows up in adoption: RLHF pipelines (InstructGPT and the early ChatGPT training recipe), robotics work like OpenAI's Dactyl hand, and game-playing agents such as the Dota 2 Five system all built on PPO rather than a bespoke alternative.
