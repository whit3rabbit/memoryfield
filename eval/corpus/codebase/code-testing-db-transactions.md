---
uuid: code-testing-db-transactions
title: "Testing: how database tests use transactions"
summary: "Each test runs in a transaction that's rolled back at the end; tests don't see each other's writes; speed ~10x vs per-test DB."
status: active
tags: [testing, database]
---
## Answer
We use the `pytest-postgresql` transactional fixture: each test
runs inside a transaction that gets rolled back at teardown.

This makes tests ~10x faster than per-test database creation,
at the cost of not testing transaction isolation. We run a
separate isolation-level test suite weekly.

