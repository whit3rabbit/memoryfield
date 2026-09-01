---
uuid: para-code-obs-request-id
title: How request correlation IDs propagate
summary: The edge mints a UUIDv7 per request, returns it as `X-Request-Id`, and every downstream log and span carries `request_id`.
---
## Answer
Every request gets a UUIDv7 assigned at the edge, before it
reaches any internal service. That value is returned to the
client in the `X-Request-Id` response header and is also forwarded
along on every internal call the request triggers.

Because it rides along through the whole call chain, `request_id`
ends up attached to every log line and every trace span produced
while handling that request. That makes it possible to pull the
complete story of a single request - across every service it
touched - just by filtering logs or traces on one ID. UUIDv7 was
chosen over UUIDv4 specifically because it's time-ordered, which
keeps IDs roughly sortable and index-friendly.
