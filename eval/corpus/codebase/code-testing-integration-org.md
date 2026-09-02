---
uuid: code-testing-integration-org
title: "Testing: how integration tests are organized"
summary: "`tests/integration/` runs against a Postgres container per test; each test gets a fresh DB, runs migrations, seeds fixtures."
status: active
tags: [testing, integration]
---
## Answer
```bash
make test-integration  # spins up Postgres via testcontainers
```
Each test:
1. Spins a Postgres container.
2. Runs migrations.
3. Loads fixtures.
4. Runs the test.
5. Tears down the container.

