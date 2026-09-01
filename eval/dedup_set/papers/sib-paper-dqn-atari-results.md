---
uuid: sib-paper-dqn-atari-results
title: Experience replay and a frozen target network are what make DQN stable
summary: DQN trains from a replay buffer of past transitions sampled randomly rather than sequentially, and bootstraps against a separate, periodically-updated target network - two mechanisms that break the correlations and moving-target instability that made naive Q-learning with neural nets diverge.
---
## Answer
Plugging a neural network directly into standard Q-learning tends to diverge, for two compounding reasons: consecutive game frames are highly correlated, and the Q-learning target itself depends on the same weights being updated, so the target keeps shifting under the network's feet.

DQN addresses both. First, an experience replay buffer stores past (state, action, reward, next-state) transitions and samples minibatches from it uniformly at random, breaking the temporal correlation between consecutive training examples.

Second, a target network - a copy of the online network's weights, frozen and only synced every N steps - computes the bootstrap target instead of the network currently being updated. This keeps the regression target stationary between syncs.

Both mechanisms are prerequisites for the 49-game result to be reproducible at all; without them, training the same architecture on the same games tends to diverge rather than converge.
