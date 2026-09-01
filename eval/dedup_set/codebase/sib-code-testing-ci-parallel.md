---
uuid: sib-code-testing-ci-parallel
title: Testing - how flaky tests are quarantined
summary: A test failing intermittently 3 times in 7 days gets auto-tagged `quarantine`, moves to a non-blocking job, and gets a tracking issue.
---
## Answer
Flaky tests are not deleted or silently skipped, since that hides
real regressions. Instead a nightly job scans the last 7 days of
CI runs, and any test that failed intermittently (passed on retry
without a code change) 3 or more times gets auto-tagged
`quarantine` in the test metadata.

Quarantined tests move out of the blocking PR and merge-queue
runs into a separate `quarantine` CI job that still runs on every
merge but does not block anything. The nightly job also opens (or
comments on) a tracking issue tagged with the test name and owner,
based on `CODEOWNERS`.

A quarantined test comes back to the blocking suite once it
passes 20 consecutive runs in the quarantine job, or after a fix
is merged and verified.
