---
uuid: code-dm-timestamptz
title: Data model: time columns use TIMESTAMPTZ not TIMESTAMP
summary: All time columns are `TIMESTAMPTZ`; we always store UTC; client-side formatting happens at render time only.
status: active
tags: [data-model, time]
---
## Answer
`TIMESTAMPTZ` (timestamp with time zone) stores the value
normalized to UTC internally. We never use plain `TIMESTAMP`
(without time zone) — those silently drop the offset and
produce confusing comparisons.

