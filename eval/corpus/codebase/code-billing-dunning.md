---
uuid: code-billing-dunning
title: "Billing: how dunning works"
summary: "Failed payments trigger `dunning_level` increments (1–4); each level fires an email and may pause the subscription at level 4."
status: active
tags: [billing, dunning]
---
## Answer
Dunning is a state machine: `dunning_level` ranges 0–4. A failed
payment increments it; a successful payment resets to 0.

Levels 1–3 fire templated emails at increasing urgency. Level 4
pauses the subscription and triggers an admin alert.

The retry schedule: 1 day, 3 days, 5 days, 7 days.

