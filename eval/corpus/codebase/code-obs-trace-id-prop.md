---
uuid: code-obs-trace-id-prop
title: Observability: what `trace_id` propagation requires
summary: Set the W3C `traceparent` header on every outgoing HTTP/gRPC call; the receiving service extracts it and starts a child span.
status: active
tags: [observability, tracing]
---
## Answer
Every outgoing HTTP/gRPC call must set the W3C `traceparent`
header. Our HTTP client and gRPC interceptors do this
automatically when the request starts a new trace or
participates in an existing one.

## Don't
Don't manually construct the `traceparent` header. The
OpenTelemetry SDK generates it with the right version flags.

