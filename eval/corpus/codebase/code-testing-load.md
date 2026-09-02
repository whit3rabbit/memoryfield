---
uuid: code-testing-load
title: "Testing: how load tests are run"
summary: "Locust scripts in `tests/load/`; run weekly against staging with a 30-min ramp + 1-hour soak; output goes to the perf dashboard."
status: active
tags: [testing, load]
---
## Answer
```bash
make load-test  # 30-min ramp, 1-hour soak against staging
```
Results land in the perf dashboard. Any p99 regression > 10%
blocks the next release.

