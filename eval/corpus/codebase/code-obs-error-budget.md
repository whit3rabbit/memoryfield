---
uuid: code-obs-error-budget
title: "Observability: what the error budget is for"
summary: "The error budget is for *risk-taking* (deploys, experiments); when 50% remains, freeze non-critical deploys and shift work to reliability."
status: active
tags: [observability, slo, policy]
---
## Answer
The error budget is the *allowance* for unreliability. You spend
it on deploys, experiments, and risky changes.

Remaining budget thresholds:
- 50%: ship normally
- 25–50%: be conservative; double-review risky changes
- <25%: freeze non-critical deploys; shift focus to reliability

