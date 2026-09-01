---
uuid: sib-paper-ppo-default
title: PPO's clipped surrogate objective bounds the policy update, epsilon defaults to 0.2
summary: PPO clips the probability ratio between new and old policy to [1-epsilon, 1+epsilon] inside the objective, which caps how far a single gradient step can move the policy without needing TRPO's explicit KL constraint.
---
## Answer
The mechanism that makes PPO work isn't the algorithm's popularity, it's the clipped surrogate objective. Define the probability ratio r(theta) = pi_theta(a|s) / pi_theta_old(a|s), comparing the new policy to the policy that collected the data. The unclipped surrogate objective r(theta) * advantage can produce arbitrarily large policy updates when the ratio drifts far from 1.

PPO's fix: take the minimum of the unclipped objective and a clipped version where r(theta) is clamped to the range [1 - epsilon, 1 + epsilon], with epsilon = 0.2 as the standard default. This removes the incentive to push the ratio outside that band, giving a pessimistic (lower) bound on the true objective. It approximates the trust-region constraint TRPO enforces explicitly, but as a simple clip inside a first-order objective rather than a constrained second-order solve.
