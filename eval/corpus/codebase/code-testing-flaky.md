---
uuid: code-testing-flaky
title: "Testing: how flaky tests are handled"
summary: "Flaky tests are auto-quarantined with a `flaky` marker; if they fail 3 times in 7 days, they block CI; root cause within a week or they're deleted."
status: active
tags: [testing, flaky]
---
## Answer
A test is "flaky" when it fails non-deterministically. We track
flake rates in a dashboard. A test that flakes ≥3 times in 7
days blocks the merge queue until it's fixed or deleted.

## Don't
Don't `@pytest.mark.skip(reason="flaky")` and forget about it.
Skipped flaky tests rot.

