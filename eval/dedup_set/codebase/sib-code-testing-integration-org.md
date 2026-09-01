---
uuid: sib-code-testing-integration-org
title: Testing - how end-to-end browser tests are organized
summary: `tests/e2e/` runs Playwright against a deployed staging environment nightly, not per-PR, seeded via API rather than direct DB writes.
---
## Answer
```bash
make test-e2e  # runs Playwright against staging
```

End-to-end tests live in `tests/e2e/` and use Playwright to drive
a real browser against the staging environment, not a locally
spun-up service. They run nightly on a schedule and on demand
before a release, but not on every PR, since a full browser suite
takes about 25 minutes and staging is a shared environment.

Each test seeds its own data by calling the app's public API
(creating a test org, a test user, etc.) rather than writing to
the database directly, since the test only has network access to
staging. Tests clean up their own seeded data via the API at the
end of the run. Screenshots and video are captured on failure and
uploaded as CI artifacts.
