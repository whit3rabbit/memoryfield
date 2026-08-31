---
uuid: paper-dqn-tricks
title: DQN: deep Q-network with experience replay and target network
summary: Two tricks stabilize Q-learning with neural networks: (1) experience replay buffer breaks temporal correlation; (2) target network updates slowly to stabilize the bootstrap target.
status: active
tags: [dqn, rl, stability]
source: https://www.nature.com/articles/nature14236
---
## Answer
Two stability tricks:

1. **Experience replay**: store transitions in a buffer; sample uniformly when training. Breaks temporal correlation between consecutive samples.

2. **Target network**: keep a separate Q-network whose parameters are updated only every C steps. The bootstrap target uses this target network, not the live one. Prevents the moving-target problem.
