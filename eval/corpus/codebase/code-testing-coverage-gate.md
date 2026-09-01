---
uuid: code-testing-coverage-gate
title: Testing: what the coverage gate is
summary: 80% line coverage on PRs; new code must be ≥ 80% or explicitly excluded with a `# pragma: no cover` and a justification.
status: active
tags: [testing, coverage]
---
## Answer
PR coverage gate: 80% line coverage on changed files.

## Don't
Don't add `# pragma: no cover` without a justification in a
comment that explains *why* the line is un-testable. CI
enforces the comment.

