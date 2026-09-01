---
uuid: code-testing-snapshots
title: Testing: how snapshot tests work
summary: Snapshot files live next to the test (`test_foo.py` → `test_foo.py.snap`); review snapshot diffs in PRs as carefully as code changes.
status: active
tags: [testing, snapshots]
---
## Answer
Snapshots are stored in `.snap` files alongside tests. The test
framework auto-updates them with `--update-snapshots`. Snapshots
must be reviewed in PRs — they're code.

## Don't
Don't blindly accept snapshot updates. Each diff is a potential
regression.

