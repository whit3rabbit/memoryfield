---
uuid: code-obs-trace-sampling
title: "Observability: how traces are sampled"
summary: "Head-based sampling at 1% baseline + tail-based at 100% for traces with errors or latency > p99; sample rate is configurable per service."
status: active
tags: [observability, tracing]
---
## Answer
Two-stage sampling:
1. Head-based: 1% baseline keep rate, set at the agent.
2. Tail-based: 100% keep for traces with errors or
   latency > p99.

This gives full visibility into the slow/long-tail traces
without drowning the storage in noise.

