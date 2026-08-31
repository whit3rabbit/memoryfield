---
uuid: code-testing-fixture-vs-factory
title: Testing: when to use a fixture vs a factory
summary: Fixtures for canonical objects (default user); factories for parameterized objects (user with custom roles, billing state).
status: active
tags: [testing, fixtures]
---
## Answer
- **Fixture**: a hardcoded, canonical instance loaded from a
  file. Use for "the default user" in 90% of tests.
- **Factory**: a programmatic builder. Use when you need
  variations (different roles, billing states, etc.).

