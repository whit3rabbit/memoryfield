---
uuid: para-code-billing-dunning
title: Billing - what happens when a payment fails
summary: A failed charge bumps dunning_level up by one on a 0-4 scale and triggers an email at levels 1-3, while level 4 pauses the subscription and alerts an admin.
---
## Answer
Think of dunning as a small state machine tracked by `dunning_level`, which runs 0 through 4. Every failed payment attempt pushes it up by one step; any successful payment immediately resets it back to 0.

At levels 1, 2, and 3 the customer gets an email, with the tone getting more urgent as the level climbs. Reaching level 4 does two things at once: the subscription gets paused, and an admin alert fires.

Retries follow a fixed schedule after the first failure: 1 day, then 3, then 5, then 7 days out.
