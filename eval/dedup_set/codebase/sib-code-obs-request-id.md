---
uuid: sib-code-obs-request-id
title: Observability - how trace sampling works
summary: Head-based sampling keeps 5% of traces at ingest; any trace containing an error is retained at 100% via tail sampling.
---
## Answer
Not every trace is stored, since storing 100% of traces at
current volume would be prohibitively expensive. Sampling
happens in two stages.

Head-based sampling runs at the edge collector: 5% of traces are
marked "keep" at the start of the request, before anything is
known about how it will resolve. That decision is embedded in the
trace context so every downstream span honors it consistently.

Tail-based sampling runs afterward at the collector layer: once a
trace is complete, any trace containing a span with an error
status, or with total latency above the service's p99 threshold,
is retained regardless of the head-sampling decision. This means
error traces are effectively kept at 100%, while ordinary
successful requests are the ones being downsampled.
