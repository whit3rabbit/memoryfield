---
uuid: code-testing-property-based
title: "Testing: property-based testing with Hypothesis"
summary: "Use Hypothesis for parsers, serializers, and pure functions; pre-generated examples are stored in `hypothesis/examples/` for reproducibility."
status: active
tags: [testing, property-based]
---
## Answer
Hypothesis generates random inputs and asserts invariants. We use
it heavily for parsers, serializers, and pure business logic.

Failures are saved as examples in `hypothesis/examples/` and
replayed on every CI run, so the bug never regresses silently.

