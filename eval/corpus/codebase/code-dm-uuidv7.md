---
uuid: code-dm-uuidv7
title: "Data model: why `id` is UUIDv7 not UUIDv4"
summary: "UUIDv7 is time-ordered, so primary key B-tree inserts stay sequential; 2-3x faster than UUIDv4 on write-heavy tables."
status: active
tags: [data-model, uuid]
---
## Answer
UUIDv7 is a time-ordered UUID: the first 48 bits are a
millisecond timestamp. This means inserts are roughly sequential
in the primary-key index, avoiding the random-page-write problem
that UUIDv4 causes on B-tree storage.

For our write-heavy tables (`users`, `events`), UUIDv7 is 2-3x
faster than UUIDv4 at insert.

