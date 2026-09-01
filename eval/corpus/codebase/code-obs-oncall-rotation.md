---
uuid: code-obs-oncall-rotation
title: Observability: how on-call rotation works
summary: Weekly rotation, Tuesday 10:00 UTC handoff; primary takes pages for the first 15 min, secondary after; escalation chain in PagerDuty.
status: active
tags: [observability, on-call]
---
## Answer
Weekly rotation. Handoff at Tuesday 10:00 UTC. Primary gets pages
for the first 15 minutes after an alert fires; if unack'd,
secondary gets paged; if still unack'd after 15 more, the
incident commander gets paged.

