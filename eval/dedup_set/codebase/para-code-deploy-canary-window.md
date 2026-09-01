---
uuid: para-code-deploy-canary-window
title: Deploy - how the canary rollout window is configured
summary: A new release first ships to 5% of pods for a 10-minute window, auto-promoting on a sub-0.5% error rate and auto-rolling-back on error spikes, latency, or excess error-budget burn.
---
## Answer
The rollout config lives in `deploy/canary.yaml`. A release starts by going to just 5% of pods, and stays there for 10 minutes before anything else happens.

If the error rate over that window stays under 0.5%, the release gets promoted and rolls forward to the rest of the fleet automatically. Rollback triggers automatically instead if any of these show up during the window: a spike in 5xx responses, p99 latency crossing 500ms, or the error budget burning down faster than 2x its normal rate.
