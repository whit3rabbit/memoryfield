---
uuid: para-code-testing-integration-org
title: Layout and lifecycle of the integration test suite
summary: Run with `make test-integration`; each test spins up its own Postgres container, migrates, seeds fixtures, then tears down.
---
## Answer
Integration tests live under `tests/integration/` and are run
with:

```bash
make test-integration
```

which brings up Postgres containers via testcontainers. The
lifecycle for each individual test is:

1. Start a fresh Postgres container just for that test.
2. Apply migrations against it.
3. Load fixture data.
4. Run the actual test body.
5. Tear the container down.

Because every test gets its own container from scratch, tests
can't leak state into each other through the database, which is a
common source of hard-to-debug flakiness in suites that share one
database across the whole run.
