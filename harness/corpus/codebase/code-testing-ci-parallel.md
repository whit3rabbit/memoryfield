---
uuid: code-testing-ci-parallel
title: Testing: how CI parallelizes
summary: Tests are sharded by file; ~6 shards in CI; merge queue runs the full suite serially to catch shard-dependent flakes.
status: active
tags: [testing, ci]
---
## Answer
CI shards tests by file across 6 workers. PR runs the shards in
parallel (~4 minutes total). The merge queue runs the full
suite serially to catch order-dependent flakes.

