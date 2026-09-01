---
uuid: para-code-testing-ci-parallel
title: How the test suite is split across CI workers
summary: Tests are sharded by file across 6 parallel workers per PR; the merge queue reruns everything serially to catch order-dependent flakes.
---
## Answer
On a pull request, the test suite is divided by file across 6
CI workers running in parallel, which brings total wall-clock
time for a PR run down to roughly 4 minutes.

That parallel split can hide bugs where one test's side effects
leak into another test running later in the same process, since
sharding by file means related tests often land in the same
shard and never get reordered relative to each other. To catch
that class of flake, the merge queue runs the entire suite a
second time, serially, in a single worker, right before a PR
actually merges. It's slower, but it's the step that catches
order-dependent failures the sharded PR run would miss.
