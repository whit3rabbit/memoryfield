"""Build the M0 labeled corpus.

Two domains:

- code/: 75 pages of memory about a fictional Python web service called
  "ledger" (auth, billing, schema migrations, deploy quirks). This mirrors
  the "codebase memory" use case from PLAN.md §7.

- papers/: 75 claim-pages drawn from a small set of well-known ML and systems
  papers (each paper contributes 5–8 individual claim pages, one per claim,
  with `source` set to a real URL or arxiv ID).

We *generate* the corpus deterministically from seeds. Generation is
scripted, not hand-typed, because:
  - hand-typed labels bias toward "easy" queries the author already
    knows the answer to
  - scripts reproduce — a fresh checkout gets the same M0 numbers
  - the structure (frontmatter conventions, body layout, stub vs L1) is
    easier to verify mechanically

Each page is a memoryfield-spec Markdown file with:
  - uuid, title, summary (the answer), status, tags
  - a body with one `## Answer` (L1) section and possibly `## Don't`,
    `## Context`, or `## Source` sections

Each query is a JSONL file: one query per line, with qid, text,
answer_uuids, stub_sufficient.
"""
from __future__ import annotations

import json
import re
import sys
import textwrap
import uuid as uuid_mod
from pathlib import Path

ROOT = Path(__file__).parent
CORPUS_ROOT = ROOT / "corpus"
CODE_DIR = CORPUS_ROOT / "codebase"
PAPERS_DIR = CORPUS_ROOT / "papers"
QCODE_DIR = ROOT / "queries" / "codebase"
QPAPERS_DIR = ROOT / "queries" / "papers"


def write_page(directory: Path, *, uuid: str, title: str, summary: str,
               tags: list[str], body: str, status: str = "active",
               source: str = "") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    fm_lines = [
        "---",
        f"uuid: {uuid}",
        f"title: {title}",
        f"summary: {summary}",
        f"status: {status}",
        f"tags: [{', '.join(tags)}]",
    ]
    if source:
        fm_lines.append(f"source: {source}")
    fm_lines.append("---")
    fm = "\n".join(fm_lines) + "\n"
    path = directory / f"{uuid}.md"
    path.write_text(fm + body + "\n", encoding="utf-8")
    return path


def write_queries(directory: Path, queries: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / "queries.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for q in queries:
            f.write(json.dumps(q) + "\n")


# ---------------------------------------------------------------------------
# code/ domain — fictional "ledger" Python web service
# ---------------------------------------------------------------------------
#
# 75 pages split into 8 categories:
#   auth (10), billing (10), migrations (10), deploy (10),
#   observability (10), testing (10), api-quirks (10), data-model (5)

CODE_PAGES = [
    # ---- auth (10) ----
    {
        "title": "Auth: rotating the JWT signing key",
        "summary": "Run `make rotate-jwt-key`; redeploys auth service in 60s; old keys valid for 5-minute overlap window.",
        "tags": ["auth", "jwt", "rotation", "ops"],
        "body": textwrap.dedent("""\
            ## Answer
            Run `make rotate-jwt-key`. That target generates a new Ed25519 keypair,
            uploads the public half to the secrets manager, and triggers a rolling
            restart of the auth service. Old keys remain valid for 300 seconds
            (configured via `JWT_OVERLAP_WINDOW`) so in-flight tokens still verify.

            ## Why the overlap
            Rotating without an overlap breaks every long-poll connection for ~30s
            of clock skew. 5 minutes is overkill for our traffic but cheap.

            ## Don't
            - Don't rotate the key by hand-editing the secrets manager. The
              makefile target also bumps the key version label that auth clients
              cache; without it, every API client re-validates against an unknown
              key id for an hour.
            - Don't rotate during the deploy window 09:00–10:00 UTC. The deploy
              itself triggers auth-service restarts and a key rotation on top
              looks identical in the logs.
            """),
        "source": "ops/runbook/auth.md#rotate-jwt",
    },
    {
        "title": "Auth: why we use Ed25519 not RSA",
        "summary": "Ed25519 is 10x faster to verify; tokens are short; we never need to encrypt them.",
        "tags": ["auth", "jwt", "design"],
        "body": textwrap.dedent("""\
            ## Answer
            We sign JWTs with Ed25519 because (a) verification is roughly 10x
            faster than RSA-2048, which matters at peak (~8k token checks/sec),
            and (b) the token header stays short enough to fit in a single TCP
            packet with our edge proxy's header limits.

            We don't need RSA's encrypt-decrypt capability — JWTs are signed, not
            encrypted. The payload is base64 but readable.

            ## Don't
            Don't propose switching to P-256 ECDSA "for compatibility". The
            legacy clients that needed P-256 were deprecated in 2024; current
            clients are all Ed25519-capable.
            """),
    },
    {
        "title": "Auth: how service-to-service tokens work",
        "summary": "Services exchange their workload identity for a 5-minute bearer token via the `auth-tokens` endpoint; the token's `aud` field is the calling service's name.",
        "tags": ["auth", "s2s", "tokens"],
        "body": textwrap.dedent("""\
            ## Answer
            A service authenticates by presenting its workload identity (a SPIFFE
            SVID issued by the cluster's trust domain) to `auth-tokens` over mTLS.
            `auth-tokens` returns a bearer JWT with a 5-minute TTL and an `aud`
            claim set to the requesting service's name.

            The receiver checks: (1) signature with the public Ed25519 key from
            secrets manager, (2) `aud` matches its own service name, (3)
            `exp > now`, (4) the SPIFFE ID is in the receiver's allowlist.

            ## Don't
            Don't cache the bearer token beyond its TTL. The auth-tokens endpoint
            issues a fresh one in <5ms; caching adds revocation complexity for
            no measurable benefit.
            """),
    },
    {
        "title": "Auth: handling a leaked token",
        "summary": "Page `#sec-incident` in Slack, run `make revoke-token <jti>`, force-rotate the affected service's identity.",
        "tags": ["auth", "incident", "tokens"],
        "body": textwrap.dedent("""\
            ## Answer
            1. Page `#sec-incident` in Slack.
            2. Run `make revoke-token <jti>` — adds the JTI to the revocation
               list and pushes it to every edge proxy within 30s.
            3. Force-rotate the affected service's workload identity (the SVID
               gets re-issued with a new serial).
            4. Post-incident: review audit logs for the token's `aud` to find
               which service accepted it during the leak window.

            ## Don't
            Don't try to revoke a single token by rotating the signing key —
            that's a sledgehammer that invalidates every active session.
            """),
        "source": "ops/runbook/auth.md#leaked-token",
    },
    {
        "title": "Auth: the difference between user JWT and service JWT",
        "summary": "User JWTs have a `sub` claim with the user ID and live 1 hour; service JWTs have an `aud` claim with the service name and live 5 minutes.",
        "tags": ["auth", "jwt", "distinction"],
        "body": textwrap.dedent("""\
            ## Answer
            Two distinct JWT kinds, both signed with the same key:

            - **User JWT**: `sub` = user UUID, `aud` = the service the user is
              calling, TTL = 1 hour. Issued after OAuth callback.
            - **Service JWT**: no `sub`, `aud` = the calling service's own name,
              TTL = 5 minutes. Issued by `auth-tokens` from a SPIFFE SVID.

            The `aud` claim is the disambiguator. A user JWT with `aud=billing`
            is valid for billing endpoints; a service JWT with `aud=billing` is
            for billing calling something else.

            ## Don't
            Don't accept a JWT whose `aud` doesn't match *your* service name,
            even if the signature verifies. That's the most common bug in
            first-time integration code.
            """),
    },
    {
        "title": "Auth: how OAuth callback validates state",
        "summary": "State is a signed nonce cookie set before the redirect; we verify it with a constant-time compare on the way back.",
        "tags": ["auth", "oauth", "csrf"],
        "body": textwrap.dedent("""\
            ## Answer
            Before redirecting to the IdP, we set a `oauth_state` cookie
            containing a 128-bit random nonce, signed with HMAC-SHA256. On the
            callback, we compare the `state` query parameter against the cookie
            value using `hmac.compare_digest`.

            The signature uses the same Ed25519 key as JWTs but in HMAC mode
            (yes, we abuse it — fine for our threat model).

            ## Don't
            Don't store the state in a server-side session — that creates a
            session for every unauthenticated visit and DoSes the session store.
            """),
    },
    {
        "title": "Auth: what `aud` claims mean in practice",
        "summary": "`aud` is the service *receiving* the token, not the service *issuing* it; check the API docs for what each endpoint expects.",
        "tags": ["auth", "jwt", "aud"],
        "body": textwrap.dedent("""\
            ## Answer
            `aud` (audience) names the service that should accept the token.
            For service-to-service auth, this is the service the calling code
            is going to make a request *to*.

            Example: when `billing` calls `inventory`, billing asks `auth-tokens`
            for a JWT with `aud=inventory`. inventory accepts it because the
            `aud` matches its own name.

            ## Don't
            Don't set `aud` to the calling service's own name. This is a
            common confusion from people used to SAML `AudienceRestriction`
            where the semantics are slightly different.
            """),
    },
    {
        "title": "Auth: where the public keys live",
        "summary": "Active keys are in `secrets://auth/jwt/active`; rotated-out keys live in `secrets://auth/jwt/history/<version>` for 30 days.",
        "tags": ["auth", "jwt", "secrets"],
        "body": textwrap.dedent("""\
            ## Answer
            Public keys are published to the secrets manager at
            `auth/jwt/active` (the current signing key) and
            `auth/jwt/history/<version>` (rotated-out keys, retained for 30
            days so overlap-window tokens still verify).

            Every service subscribes to changes via the secrets manager's
            watch API and caches the active key in memory.

            ## Don't
            Don't fetch the key on every JWT verification. The watch subscription
            updates the in-memory cache within 100ms of rotation; re-fetching
            adds 5–10ms per verify and trashes the secrets manager's quota.
            """),
    },
    {
        "title": "Auth: what the token `kid` header means",
        "summary": "`kid` is the key version label; verifiers must check it against the active key set, not the signing key's URL.",
        "tags": ["auth", "jwt", "kid"],
        "body": textwrap.dedent("""\
            ## Answer
            `kid` (key ID) is a version label that identifies which key from
            the secrets manager signed this token. Format: `v<n>-<sha256[:8]>`
            (e.g., `v42-7a3b9c1e`).

            Verifiers must look up the key by `kid`, not by a fixed URL — when
            the key rotates, the URL stays the same but the `kid` changes.

            ## Don't
            Don't trust a token whose `kid` is not in your active key set,
            even if the signature math checks out. Old-key tokens should have
            expired by now.
            """),
    },
    {
        "title": "Auth: why we don't use sessions",
        "summary": "Sessions require server-side state; JWTs are stateless and let us scale auth-free at the edge.",
        "tags": ["auth", "design", "sessions"],
        "body": textwrap.dedent("""\
            ## Answer
            We use stateless JWTs because:
            1. The edge proxy can verify tokens without a database round-trip.
            2. There's no session store to shard, replicate, or evict.
            3. Logout is just "client deletes the token" — for our threat
               model (low-value sessions, short TTLs) this is fine.

            The tradeoff: revocation is coarser (full key rotation) than
            per-session invalidation. We mitigate with short TTLs (1 hour user,
            5 minutes service).
            """),
    },
    # ---- billing (10) ----
    {
        "title": "Billing: how invoice lines are computed",
        "summary": "Each line is `(unit_price × quantity) × proration_factor` where proration_factor is the fraction of the billing period the line covers.",
        "tags": ["billing", "invoices", "math"],
        "body": textwrap.dedent("""\
            ## Answer
            `line_total = unit_price * quantity * proration_factor`

            `proration_factor` is calculated from the line's `service_start`
            and `service_end` against the billing period boundaries. A line
            spanning the full period has factor 1.0; a line starting halfway
            through has factor 0.5.

            All math uses `decimal.Decimal` with 6 decimal places of
            intermediate precision. Don't use floats.
            """),
    },
    {
        "title": "Billing: why we don't store currency conversions",
        "summary": "We charge in the customer's billing currency; conversions happen at payout time via the recorded FX rate snapshot.",
        "tags": ["billing", "currency", "fx"],
        "body": textwrap.dedent("""\
            ## Answer
            Invoice amounts are stored in the customer's billing currency.
            When we pay out to the customer's bank in a different currency,
            we apply the FX rate at the time of payout, not at invoice time.

            This means we never need to retroactively adjust invoices when
            exchange rates move — a regulator-friendly property.

            ## Don't
            Don't compute the converted amount at invoice time and store it.
            That creates an FX-adjustment line item that auditors hate.
            """),
    },
    {
        "title": "Billing: the proration edge case at month boundaries",
        "summary": "Lines that start or end exactly on a billing period boundary get factor 1.0 (boundary-inclusive); we use the half-open interval `(start, end]`.",
        "tags": ["billing", "proration", "edge-case"],
        "body": textwrap.dedent("""\
            ## Answer
            Proration uses the half-open interval `(start, end]`. A line with
            `service_start = 2026-01-01 00:00:00 UTC` and
            `service_end = 2026-02-01 00:00:00 UTC` covers the entire January
            period (factor 1.0), even though it touches both endpoints.

            The unit tests in `test_billing_proration.py` have a matrix of all
            four (start_inclusive, end_inclusive) combinations.

            ## Don't
            Don't switch to `[start, end]` (closed) — it double-counts
            midnight boundaries when two lines abut.
            """),
        "source": "tests/test_billing_proration.py",
    },
    {
        "title": "Billing: handling refunds",
        "summary": "Refunds are negative invoice lines with a `refund_of` reference to the original line; they don't modify the original line.",
        "tags": ["billing", "refunds"],
        "body": textwrap.dedent("""\
            ## Answer
            A refund creates a *new* invoice line with a negative amount and
            a `refund_of` foreign key to the original line. We never modify
            the original line.

            This preserves the audit trail: a customer can see exactly what
            they were charged and exactly what was refunded, in order.
            """),
    },
    {
        "title": "Billing: what `tax_mode: inclusive` means",
        "summary": "Prices already include tax; the invoice's `tax` field is computed as `total - subtotal / (1 + tax_rate)`.",
        "tags": ["billing", "tax"],
        "body": textwrap.dedent("""\
            ## Answer
            `tax_mode: inclusive` means the listed prices contain tax already
            (common in EU B2C). To back out the tax portion:
            `tax = total - subtotal / (1 + tax_rate)`.

            Compare to `tax_mode: exclusive` (US B2B) where
            `tax = subtotal * tax_rate`.
            """),
    },
    {
        "title": "Billing: how trial periods are billed",
        "summary": "Trials generate zero-amount invoice lines with `proration_factor = 0`; they exist only for audit trail.",
        "tags": ["billing", "trial"],
        "body": textwrap.dedent("""\
            ## Answer
            Trials create invoice lines with `quantity = 0` (or `unit_price = 0`,
            depending on the line type). The line is still emitted and
            finalized, so the audit trail shows "customer was on trial
            2026-03-01 to 2026-03-15" even though no money changed hands.
            """),
    },
    {
        "title": "Billing: idempotency key for invoice creation",
        "summary": "`Idempotency-Key` header on POST /invoices; replays with the same key return the original invoice without re-charging.",
        "tags": ["billing", "idempotency"],
        "body": textwrap.dedent("""\
            ## Answer
            `POST /invoices` accepts an `Idempotency-Key` header. We store the
            key + invoice UUID in Redis for 24 hours. A replay with the same
            key returns the original invoice (200 OK) instead of creating a
            duplicate.

            Keys are scoped to the customer ID; two customers can use the same
            key without conflict.
            """),
    },
    {
        "title": "Billing: how dunning works",
        "summary": "Failed payments trigger `dunning_level` increments (1–4); each level fires an email and may pause the subscription at level 4.",
        "tags": ["billing", "dunning"],
        "body": textwrap.dedent("""\
            ## Answer
            Dunning is a state machine: `dunning_level` ranges 0–4. A failed
            payment increments it; a successful payment resets to 0.

            Levels 1–3 fire templated emails at increasing urgency. Level 4
            pauses the subscription and triggers an admin alert.

            The retry schedule: 1 day, 3 days, 5 days, 7 days.
            """),
    },
    {
        "title": "Billing: the payout reconciliation job",
        "summary": "Runs daily at 02:00 UTC; matches ledger entries against Stripe payouts and flags discrepancies > $0.01.",
        "tags": ["billing", "payout", "job"],
        "body": textwrap.dedent("""\
            ## Answer
            `payout-reconciler` runs as a cron at 02:00 UTC daily. It reads
            Stripe's payout report, joins against our `ledger_entries` table
            on the Stripe transaction ID, and writes any mismatch > $0.01 to
            `payout_discrepancies` for manual review.

            Tolerance of $0.01 is intentional — FX rounding between charge
            and payout can produce sub-cent noise.
            """),
    },
    {
        "title": "Billing: stripe webhook signature verification",
        "summary": "Verify with `stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)`; never trust the raw payload.",
        "tags": ["billing", "stripe", "webhook"],
        "body": textwrap.dedent("""\
            ## Answer
            Always verify Stripe webhook signatures with the official SDK:
            `stripe.Webhook.construct_event(request.body, sig_header, SECRET)`.
            This raises on bad signature.

            ## Don't
            Don't process the webhook before verification. Several real
            attacks have involved replaying captured Stripe payloads to
            duplicate fulfillment.
            """),
    },
    # ---- migrations (10) ----
    {
        "title": "Migrations: how to add a NOT NULL column safely",
        "summary": "Three-step: add nullable column, backfill in batches, set NOT NULL. Each step is its own migration; never combine.",
        "tags": ["migrations", "schema", "safety"],
        "body": textwrap.dedent("""\
            ## Answer
            Three separate migrations, applied in order:

            1. `ALTER TABLE users ADD COLUMN phone TEXT;` (nullable)
            2. Backfill script in batches of 10k rows, idempotent.
            3. `ALTER TABLE users ALTER COLUMN phone SET NOT NULL;`

            Combining these into one migration locks the table for the full
            backfill duration on large tables.

            ## Don't
            Don't use a single `ALTER TABLE` with a DEFAULT for the backfill —
            it rewrites every row in place.
            """),
    },
    {
        "title": "Migrations: online vs offline schema changes",
        "summary": "Online (concurrent index creation, NOT NULL via check constraint) takes longer but doesn't lock; offline takes seconds but blocks all writes.",
        "tags": ["migrations", "schema"],
        "body": textwrap.dedent("""\
            ## Answer
            Two modes:
            - **Online**: uses Postgres features that don't take an
              ACCESS EXCLUSIVE lock. Safe to run during peak traffic.
              Examples: `CREATE INDEX CONCURRENTLY`, adding NOT NULL via a
              CHECK constraint then validating.
            - **Offline**: takes the heavy lock briefly. Faster but causes
              write-stall on large tables. Used only when online isn't
              possible (e.g., changing a column's TYPE).
            """),
    },
    {
        "title": "Migrations: why we never drop a column in the same release",
        "summary": "Two-release rule: release N removes all code that reads the column; release N+1 drops it. One release to find stragglers.",
        "tags": ["migrations", "schema", "discipline"],
        "body": textwrap.dedent("""\
            ## Answer
            Two-release rule. If release 47 stops reading `users.legacy_id`,
            release 47 may *not* drop the column. Release 48 may.

            The gap catches code paths that still read the old column —
            those code paths will start erroring in release 47's logs,
            giving you a release to find and fix them before the column
            disappears entirely.
            """),
    },
    {
        "title": "Migrations: the `lock_timeout` setting",
        "summary": "Set `lock_timeout = '5s'` at the top of every migration; migration aborts if it can't acquire the lock in 5 seconds, avoiding queue buildup.",
        "tags": ["migrations", "ops", "safety"],
        "body": textwrap.dedent("""\
            ## Answer
            Every migration file starts with
            `SET lock_timeout = '5s';`

            If the migration can't get the lock it needs within 5s, it errors
            out. The migration runner retries with exponential backoff. This
            prevents a slow migration from blocking other migrations behind it
            in the queue.
            """),
    },
    {
        "title": "Migrations: testing a destructive change",
        "summary": "Restore prod snapshot to staging, run the migration, run the full integration suite, then run a sampling query to confirm row counts match.",
        "tags": ["migrations", "testing"],
        "body": textwrap.dedent("""\
            ## Answer
            1. Take a prod snapshot from last night's backup, restore to staging.
            2. Apply the migration to staging.
            3. Run `make test-integration-staging` — full suite against real-
               ish data.
            4. Spot-check row counts on the top 10 tables against prod.

            Don't trust migrations that have only been tested against a
            10-row development database.
            """),
    },
    {
        "title": "Migrations: how to rename a column safely",
        "summary": "Three-release sequence: add new column, dual-write from old, backfill, dual-read with old-precedence, drop old. ~6 weeks.",
        "tags": ["migrations", "schema", "rename"],
        "body": textwrap.dedent("""\
            ## Answer
            The expand-contract pattern, three releases:
            - **Release N**: add `users.display_name`; keep writing to
              `users.name`. Backfill `display_name` once.
            - **Release N+1**: write to both; read from `display_name` with
              fallback to `name`. Update application code gradually.
            - **Release N+2**: stop writing to `name`; the wait period
              before drop is your call (we use 6 weeks).
            - **Release N+3**: drop `users.name`.
            """),
    },
    {
        "title": "Migrations: the audit log table",
        "summary": "Every migration records `(migration_id, applied_at, applied_by, sha256, reverted: bool)` in `schema_migrations`; never delete rows.",
        "tags": ["migrations", "audit"],
        "body": textwrap.dedent("""\
            ## Answer
            `schema_migrations` is append-only:
            ```
            migration_id | applied_at | applied_by | sha256 | reverted
            ```

            Rows are never deleted (even for reverted migrations). The
            `reverted` flag distinguishes forward and back.
            """),
    },
    {
        "title": "Migrations: zero-downtime schema changes cheat sheet",
        "summary": "Add column → dual-write → backfill → dual-read → drop old column. Each step is a separate deploy.",
        "tags": ["migrations", "reference"],
        "body": textwrap.dedent("""\
            ## Answer
            Five deploys to change a column's shape safely:
            1. Add the new shape as a nullable column.
            2. Dual-write: every write goes to both old and new.
            3. Backfill: one-shot script copying old to new.
            4. Dual-read: read new, fall back to old, verify the diff.
            5. Drop the old column in a later release.
            """),
    },
    {
        "title": "Migrations: how to roll back",
        "summary": "Every migration has a paired `down.sql`; the rollback path is `apply <N-1> --rollback`. Reversible migrations are the default; irreversible ones require a sign-off.",
        "tags": ["migrations", "rollback"],
        "body": textwrap.dedent("""\
            ## Answer
            Reversible migrations: each `up.sql` has a paired `down.sql` that
            exactly undoes it. Rollback is `apply <N-1> --rollback`.

            Irreversible migrations (data loss, type changes) require a
            documented sign-off in the PR and a `down.sql` that errors with
            "irreversible — restore from backup".
            """),
    },
    {
        "title": "Migrations: the difference between `up` and `expand`",
        "summary": "`up` migrations change schema; `expand` migrations also deploy code that dual-writes/dual-reads; never use them interchangeably.",
        "tags": ["migrations", "vocabulary"],
        "body": textwrap.dedent("""\
            ## Answer
            - `up.sql`: schema-only change.
            - `expand.sql`: schema + code that writes the new shape (in
              parallel with the old) and/or reads from the new shape (with
              fallback to the old).
            - `contract.sql`: schema + code that stops reading/writing the
              old shape.
            """),
    },
    # ---- deploy (10) ----
    {
        "title": "Deploy: the canary window",
        "summary": "New release goes to 5% of pods for 10 minutes; if error rate < 0.5%, rolls forward; otherwise rolls back automatically.",
        "tags": ["deploy", "canary"],
        "body": textwrap.dedent("""\
            ## Answer
            Configured in `deploy/canary.yaml`:
            - 5% traffic for 10 minutes
            - promotion gate: error rate < 0.5% over the window
            - rollback: any of (5xx spike, latency p99 > 500ms, error budget
              burn > 2x normal)
            """),
    },
    {
        "title": "Deploy: how to roll back a bad release",
        "summary": "`kubectl rollout undo deployment/<service>`; rollback is a forward operation and takes ~90 seconds end-to-end.",
        "tags": ["deploy", "rollback"],
        "body": textwrap.dedent("""\
            ## Answer
            `kubectl rollout undo deployment/<service>` re-deploys the
            previous image. Takes ~90s for full pod replacement at our scale.

            For database-coupled rollbacks, also run
            `make migrate-down <N>` if the release includes a schema change.
            """),
    },
    {
        "title": "Deploy: why we use immutable image tags",
        "summary": "Tags are git SHAs (e.g., `billing:a7c9d2e`), not semver; you can never deploy the same tag twice with different code.",
        "tags": ["deploy", "immutability"],
        "body": textwrap.dedent("""\
            ## Answer
            Every image tag is `<service>:<git-sha>`. The tag is set at
            build time and never changed. If you want to re-deploy "the same
            code", you re-tag from the same SHA — but you can never have two
            different builds share a tag.

            This means rollbacks are always to a specific known commit,
            not "the thing that was at this tag yesterday".
            """),
    },
    {
        "title": "Deploy: the deploy freeze calendar",
        "summary": "No deploys between Dec 20–Jan 3 (holidays) and during the all-hands on the second Tuesday of each month.",
        "tags": ["deploy", "policy"],
        "body": textwrap.dedent("""\
            ## Answer
            Two standing freeze windows:
            - **Holiday freeze**: Dec 20 (00:00 UTC) to Jan 3 (00:00 UTC).
            - **All-hands freeze**: all-hands day, 09:00–17:00 local time.

            Exceptions require a `deploy-exception` PR label and an incident
            commander's sign-off.
            """),
    },
    {
        "title": "Deploy: feature flag rollout order",
        "summary": "Internal users → 1% → 10% → 50% → 100%; each step waits ≥24 hours and requires no SLO regression.",
        "tags": ["deploy", "feature-flags"],
        "body": textwrap.dedent("""\
            ## Answer
            Gradual rollout percentages: 0, 1, 10, 50, 100. Gating criteria:
            - Each step ≥ 24 hours
            - No SLO regression on p99 latency or error rate
            - Manual checkpoint at 50% (review dashboards)
            """),
    },
    {
        "title": "Deploy: pre-deploy checklist",
        "summary": "Tests green, migrations applied to staging, dashboards reviewed, on-call notified, rollback plan documented.",
        "tags": ["deploy", "checklist"],
        "body": textwrap.dedent("""\
            ## Answer
            - [ ] CI green for the commit being deployed
            - [ ] Schema migrations tested on staging snapshot
            - [ ] Dashboards reviewed for the previous 24h
            - [ ] On-call notified in #deploys
            - [ ] Rollback command documented in the deploy PR
            """),
    },
    {
        "title": "Deploy: how pod disruption budgets work",
        "summary": "PDB `minAvailable=1` ensures at least one pod stays up during voluntary disruptions; protects against rolling deploys that drain too aggressively.",
        "tags": ["deploy", "k8s"],
        "body": textwrap.dedent("""\
            ## Answer
            Every service has a `PodDisruptionBudget` of `minAvailable: 1`.
            During voluntary disruptions (rolling deploy, node drain), the
            scheduler respects the PDB and won't evict the last pod.

            For critical services the PDB is `minAvailable: 2` (or
            percentages like `60%` for larger deployments).
            """),
    },
    {
        "title": "Deploy: the difference between a deploy and a release",
        "summary": "Deploy = new code in production; release = new code serving user traffic. Feature flags separate the two.",
        "tags": ["deploy", "vocabulary"],
        "body": textwrap.dedent("""\
            ## Answer
            - **Deploy**: a new image is running in production. May serve no
              user traffic if all features are behind flags.
            - **Release**: a feature flag is enabled for some users.

            We deploy continuously (many times per day) and release in
            larger, slower steps (per the rollout schedule).
            """),
    },
    {
        "title": "Deploy: how to debug a stuck rollout",
        "summary": "Check `kubectl rollout status`, pod events, image pull status, and the readiness probe; 80% of stuck rollouts are image pull errors.",
        "tags": ["deploy", "debugging"],
        "body": textwrap.dedent("""\
            ## Answer
            1. `kubectl rollout status deployment/<svc>` — confirms it's stuck.
            2. `kubectl describe pod <pod>` — events show image pull errors,
               OOM kills, readiness probe failures.
            3. 80% of stuck rollouts in our experience are image pull errors
               (registry auth expired, rate limit, network).
            """),
    },
    {
        "title": "Deploy: the deploy log format",
        "summary": "Each deploy emits a structured log with `deploy_id, service, image, sha, deployer, started_at, completed_at`; queries against this drive the deploy dashboard.",
        "tags": ["deploy", "observability"],
        "body": textwrap.dedent("""\
            ## Answer
            ```
            deploy_id: dpl_2026_03_15_billing_a7c9d2e
            service: billing
            image: billing:a7c9d2e
            sha: a7c9d2e
            deployer: alice
            started_at: 2026-03-15T14:32:00Z
            completed_at: 2026-03-15T14:33:30Z
            ```
            """),
    },
    # ---- observability (10) ----
    {
        "title": "Observability: the SLO for billing endpoints",
        "summary": "99.95% availability over 30-day window; error budget is 21.6 minutes of downtime per month.",
        "tags": ["observability", "slo", "billing"],
        "body": textwrap.dedent("""\
            ## Answer
            Billing endpoints target 99.95% success rate, measured over a
            30-day rolling window. The error budget is 0.05% × 30d =
            ~21.6 minutes/month of permitted downtime.

            Below 50% budget remaining, all hands shift focus to reliability
            work and freeze non-critical deploys.
            """),
    },
    {
        "title": "Observability: how traces are sampled",
        "summary": "Head-based sampling at 1% baseline + tail-based at 100% for traces with errors or latency > p99; sample rate is configurable per service.",
        "tags": ["observability", "tracing"],
        "body": textwrap.dedent("""\
            ## Answer
            Two-stage sampling:
            1. Head-based: 1% baseline keep rate, set at the agent.
            2. Tail-based: 100% keep for traces with errors or
               latency > p99.

            This gives full visibility into the slow/long-tail traces
            without drowning the storage in noise.
            """),
    },
    {
        "title": "Observability: the alerting severity ladder",
        "summary": "P5 = info (logged); P4 = warning (Slack); P3 = page primary on-call; P2 = page secondary; P1 = wake everyone.",
        "tags": ["observability", "alerting"],
        "body": textwrap.dedent("""\
            ## Answer
            - **P5**: logged, no notification.
            - **P4**: Slack channel, no page.
            - **P3**: page primary on-call.
            - **P2**: page secondary on-call (still up after 15 min).
            - **P1**: page everyone on the team + incident commander.
            """),
    },
    {
        "title": "Observability: what `trace_id` propagation requires",
        "summary": "Set the W3C `traceparent` header on every outgoing HTTP/gRPC call; the receiving service extracts it and starts a child span.",
        "tags": ["observability", "tracing"],
        "body": textwrap.dedent("""\
            ## Answer
            Every outgoing HTTP/gRPC call must set the W3C `traceparent`
            header. Our HTTP client and gRPC interceptors do this
            automatically when the request starts a new trace or
            participates in an existing one.

            ## Don't
            Don't manually construct the `traceparent` header. The
            OpenTelemetry SDK generates it with the right version flags.
            """),
    },
    {
        "title": "Observability: dashboard naming convention",
        "summary": "Service-name first, then use case (e.g., `billing: latency`, `billing: errors`); one dashboard per service + use case pair, never per query.",
        "tags": ["observability", "dashboards"],
        "body": textwrap.dedent("""\
            ## Answer
            `<service>: <use-case>` (e.g., `billing: latency`,
            `auth: token issuance`). One dashboard per (service, use-case)
            pair.

            ## Don't
            Don't make a "kitchen sink" dashboard with everything. Those
            never load and nobody reads them.
            """),
    },
    {
        "title": "Observability: log levels in production",
        "summary": "Default INFO; DEBUG only when actively debugging, scoped to one service for ≤30 minutes, never in a steady-state service.",
        "tags": ["observability", "logging"],
        "body": textwrap.dedent("""\
            ## Answer
            - **INFO**: normal operation events.
            - **DEBUG**: turned on per-service when debugging. Auto-revert
              after 30 minutes via the log-level controller.
            - **WARN/ERROR**: genuine anomalies.
            """),
    },
    {
        "title": "Observability: how on-call rotation works",
        "summary": "Weekly rotation, Tuesday 10:00 UTC handoff; primary takes pages for the first 15 min, secondary after; escalation chain in PagerDuty.",
        "tags": ["observability", "on-call"],
        "body": textwrap.dedent("""\
            ## Answer
            Weekly rotation. Handoff at Tuesday 10:00 UTC. Primary gets pages
            for the first 15 minutes after an alert fires; if unack'd,
            secondary gets paged; if still unack'd after 15 more, the
            incident commander gets paged.
            """),
    },
    {
        "title": "Observability: what the error budget is for",
        "summary": "The error budget is for *risk-taking* (deploys, experiments); when 50% remains, freeze non-critical deploys and shift work to reliability.",
        "tags": ["observability", "slo", "policy"],
        "body": textwrap.dedent("""\
            ## Answer
            The error budget is the *allowance* for unreliability. You spend
            it on deploys, experiments, and risky changes.

            Remaining budget thresholds:
            - 50%: ship normally
            - 25–50%: be conservative; double-review risky changes
            - <25%: freeze non-critical deploys; shift focus to reliability
            """),
    },
    {
        "title": "Observability: what counts as a user-facing error",
        "summary": "Any 5xx response to a request that originated from a user (not a service-to-service call) and was not a 4xx due to bad client input.",
        "tags": ["observability", "metrics"],
        "body": textwrap.dedent("""\
            ## Answer
            For SLO purposes:
            - User-facing 5xx → counts as error.
            - 4xx (except 429 rate-limit) → counts as error (caller did
              something wrong).
            - Service-to-service 5xx → counts only on the originating service.
            """),
    },
    {
        "title": "Observability: how request IDs work",
        "summary": "Generated at the edge (UUIDv7), propagated via `X-Request-Id` header, included in every log line and trace span for that request.",
        "tags": ["observability", "correlation"],
        "body": textwrap.dedent("""\
            ## Answer
            Edge generates a UUIDv7 per request, sets `X-Request-Id`
            response header, and propagates it through every internal call.
            Every log line and trace span for that request includes
            `request_id`.
            """),
    },
    # ---- testing (10) ----
    {
        "title": "Testing: how integration tests are organized",
        "summary": "`tests/integration/` runs against a Postgres container per test; each test gets a fresh DB, runs migrations, seeds fixtures.",
        "tags": ["testing", "integration"],
        "body": textwrap.dedent("""\
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
            """),
    },
    {
        "title": "Testing: when to use a fixture vs a factory",
        "summary": "Fixtures for canonical objects (default user); factories for parameterized objects (user with custom roles, billing state).",
        "tags": ["testing", "fixtures"],
        "body": textwrap.dedent("""\
            ## Answer
            - **Fixture**: a hardcoded, canonical instance loaded from a
              file. Use for "the default user" in 90% of tests.
            - **Factory**: a programmatic builder. Use when you need
              variations (different roles, billing states, etc.).
            """),
    },
    {
        "title": "Testing: how to mock external HTTP calls",
        "summary": "Use `responses` (requests) or `httpx_mock` (httpx); never use `unittest.mock.patch` on `requests.get` directly.",
        "tags": ["testing", "mocking"],
        "body": textwrap.dedent("""\
            ## Answer
            For `requests`-based code, use the `responses` library. For
            `httpx`, use `httpx_mock`. Both intercept at the transport
            layer and don't require patching internals.

            ## Don't
            Don't `unittest.mock.patch('requests.get')` — it bypasses
            transport-level concerns (TLS, retries).
            """),
    },
    {
        "title": "Testing: what the coverage gate is",
        "summary": "80% line coverage on PRs; new code must be ≥ 80% or explicitly excluded with a `# pragma: no cover` and a justification.",
        "tags": ["testing", "coverage"],
        "body": textwrap.dedent("""\
            ## Answer
            PR coverage gate: 80% line coverage on changed files.

            ## Don't
            Don't add `# pragma: no cover` without a justification in a
            comment that explains *why* the line is un-testable. CI
            enforces the comment.
            """),
    },
    {
        "title": "Testing: how flaky tests are handled",
        "summary": "Flaky tests are auto-quarantined with a `flaky` marker; if they fail 3 times in 7 days, they block CI; root cause within a week or they're deleted.",
        "tags": ["testing", "flaky"],
        "body": textwrap.dedent("""\
            ## Answer
            A test is "flaky" when it fails non-deterministically. We track
            flake rates in a dashboard. A test that flakes ≥3 times in 7
            days blocks the merge queue until it's fixed or deleted.

            ## Don't
            Don't `@pytest.mark.skip(reason="flaky")` and forget about it.
            Skipped flaky tests rot.
            """),
    },
    {
        "title": "Testing: property-based testing with Hypothesis",
        "summary": "Use Hypothesis for parsers, serializers, and pure functions; pre-generated examples are stored in `hypothesis/examples/` for reproducibility.",
        "tags": ["testing", "property-based"],
        "body": textwrap.dedent("""\
            ## Answer
            Hypothesis generates random inputs and asserts invariants. We use
            it heavily for parsers, serializers, and pure business logic.

            Failures are saved as examples in `hypothesis/examples/` and
            replayed on every CI run, so the bug never regresses silently.
            """),
    },
    {
        "title": "Testing: how snapshot tests work",
        "summary": "Snapshot files live next to the test (`test_foo.py` → `test_foo.py.snap`); review snapshot diffs in PRs as carefully as code changes.",
        "tags": ["testing", "snapshots"],
        "body": textwrap.dedent("""\
            ## Answer
            Snapshots are stored in `.snap` files alongside tests. The test
            framework auto-updates them with `--update-snapshots`. Snapshots
            must be reviewed in PRs — they're code.

            ## Don't
            Don't blindly accept snapshot updates. Each diff is a potential
            regression.
            """),
    },
    {
        "title": "Testing: how load tests are run",
        "summary": "Locust scripts in `tests/load/`; run weekly against staging with a 30-min ramp + 1-hour soak; output goes to the perf dashboard.",
        "tags": ["testing", "load"],
        "body": textwrap.dedent("""\
            ## Answer
            ```bash
            make load-test  # 30-min ramp, 1-hour soak against staging
            ```
            Results land in the perf dashboard. Any p99 regression > 10%
            blocks the next release.
            """),
    },
    {
        "title": "Testing: how database tests use transactions",
        "summary": "Each test runs in a transaction that's rolled back at the end; tests don't see each other's writes; speed ~10x vs per-test DB.",
        "tags": ["testing", "database"],
        "body": textwrap.dedent("""\
            ## Answer
            We use the `pytest-postgresql` transactional fixture: each test
            runs inside a transaction that gets rolled back at teardown.

            This makes tests ~10x faster than per-test database creation,
            at the cost of not testing transaction isolation. We run a
            separate isolation-level test suite weekly.
            """),
    },
    {
        "title": "Testing: how CI parallelizes",
        "summary": "Tests are sharded by file; ~6 shards in CI; merge queue runs the full suite serially to catch shard-dependent flakes.",
        "tags": ["testing", "ci"],
        "body": textwrap.dedent("""\
            ## Answer
            CI shards tests by file across 6 workers. PR runs the shards in
            parallel (~4 minutes total). The merge queue runs the full
            suite serially to catch order-dependent flakes.
            """),
    },
    # ---- api-quirks (10) ----
    {
        "title": "API: why GET /users returns paginated cursors",
        "summary": "Cursor-based pagination on `created_at + id`; `next_cursor` is opaque, don't parse it; offsets would be O(n) on large tables.",
        "tags": ["api", "pagination"],
        "body": textwrap.dedent("""\
            ## Answer
            `GET /users?cursor=<opaque>` returns up to 100 results ordered
            by `(created_at DESC, id DESC)`. The cursor is an opaque
            base64-encoded JSON; do not parse it client-side.

            Offset pagination would be O(offset) on `users` once it grows
            past ~1M rows.
            """),
    },
    {
        "title": "API: rate limiting per API key",
        "summary": "Token bucket: 1000 req/min sustained + burst of 100; `429` includes `X-RateLimit-Reset` header in seconds.",
        "tags": ["api", "rate-limit"],
        "body": textwrap.dedent("""\
            ## Answer
            Per-API-key rate limit: 1000 req/min sustained, burst of 100.
            On limit, server returns 429 with `X-RateLimit-Reset` (seconds
            until reset).

            ## Don't
            Don't hammer the API when you get a 429. The reset header tells
            you when to retry.
            """),
    },
    {
        "title": "API: bulk endpoints and their request shapes",
        "summary": "`POST /users/bulk` accepts an array of ≤500 create requests in one call; each item gets its own status in the response array.",
        "tags": ["api", "bulk"],
        "body": textwrap.dedent("""\
            ## Answer
            `POST /users/bulk` accepts up to 500 user-create requests in a
            single call. The response is an array of per-item statuses
            (success or error), not a single success/fail response.

            ## Don't
            Don't use `POST /users` in a loop. The bulk endpoint is 10x
            faster and doesn't blow your rate limit.
            """),
    },
    {
        "title": "API: how versioning works",
        "summary": "URL path version (`/v1/`, `/v2/`); the `Accept` header is *not* used for version negotiation.",
        "tags": ["api", "versioning"],
        "body": textwrap.dedent("""\
            ## Answer
            Version is in the URL path: `/v1/users`, `/v2/users`. We do not
            honor `Accept: application/vnd.ledger.v2+json` style version
            headers.

            ## Don't
            Don't add an `API-Version` header — clients keep forgetting it,
            and we keep forgetting to validate it.
            """),
    },
    {
        "title": "API: the difference between 401 and 403",
        "summary": "401 = no/invalid auth; 403 = auth valid but caller lacks permission. We always return 403 (never 404) for forbidden resources to avoid resource enumeration.",
        "tags": ["api", "auth", "status-codes"],
        "body": textwrap.dedent("""\
            ## Answer
            - **401 Unauthorized**: missing or invalid auth.
            - **403 Forbidden**: auth valid but the caller can't access
              this resource.

            We always return 403 for forbidden resources (never 404) to
            make resource enumeration harder.
            """),
    },
    {
        "title": "API: why errors return RFC 7807 problem details",
        "summary": "Errors are JSON `application/problem+json` with `type`, `title`, `status`, `detail`, `instance`; clients can render `title` and `detail` directly.",
        "tags": ["api", "errors"],
        "body": textwrap.dedent("""\
            ## Answer
            Error responses are `application/problem+json`:
            ```json
            {
              "type": "https://ledger.example.com/errors/insufficient-funds",
              "title": "Insufficient funds",
              "status": 402,
              "detail": "Account has $12.50; transfer requires $50.00",
              "instance": "/v1/transfers"
            }
            ```
            The `type` URL is human-readable documentation.
            """),
    },
    {
        "title": "API: what `expand` parameters do",
        "summary": "Pass `expand[]=customer` to inline related objects; one level deep by default, recursion requires `expand[]=customer.invoices`.",
        "tags": ["api", "expand"],
        "body": textwrap.dedent("""\
            ## Answer
            `?expand[]=customer` inlines the related `customer` object in the
            response instead of returning just its ID. Multiple expands:
            `?expand[]=customer&expand[]=line_items`.

            Nested: `?expand[]=customer.invoices` (one level deeper, by
            request only — otherwise unbounded).
            """),
    },
    {
        "title": "API: idempotency keys and request bodies",
        "summary": "`Idempotency-Key` ties a response to a (key, body) pair; replaying with the same key but different body returns 422.",
        "tags": ["api", "idempotency"],
        "body": textwrap.dedent("""\
            ## Answer
            The idempotency cache stores `(key, body_hash) → response`. A
            replay with the same key but a different body returns 422
            (`Idempotency-Key reused with different request`).

            ## Don't
            Don't reuse an idempotency key across unrelated requests. It
            only protects you within the same logical operation.
            """),
    },
    {
        "title": "API: how webhook signatures are verified",
        "summary": "`X-Ledger-Signature: t=<unix>,v1=<hex>`; compute HMAC-SHA256 over `t.body` with the webhook secret; reject if `|now - t| > 5min`.",
        "tags": ["api", "webhooks"],
        "body": textwrap.dedent("""\
            ## Answer
            Webhook payload:
            ```
            X-Ledger-Signature: t=1700000000,v1=4f3a2b1c...
            ```
            Verify by:
            1. Reject if `|now - t| > 300s` (replay protection).
            2. Compute HMAC-SHA256 over `<t>.<body>` with the webhook secret.
            3. Compare with `v1` using `hmac.compare_digest`.
            """),
    },
    {
        "title": "API: graceful shutdown behavior",
        "summary": "On SIGTERM, server stops accepting new requests, drains in-flight ones up to 30s, then exits non-zero if any are still running.",
        "tags": ["api", "lifecycle"],
        "body": textwrap.dedent("""\
            ## Answer
            On SIGTERM:
            1. Stop accepting new connections.
            2. Wait for in-flight requests up to 30s.
            3. Force-exit with code 1 if any are still running.

            ## Don't
            Don't set the graceful-shutdown timeout above 30s — it makes
            pod replacement visibly slow during deploys.
            """),
    },
    # ---- data-model (5) ----
    {
        "title": "Data model: why `id` is UUIDv7 not UUIDv4",
        "summary": "UUIDv7 is time-ordered, so primary key B-tree inserts stay sequential; 2-3x faster than UUIDv4 on write-heavy tables.",
        "tags": ["data-model", "uuid"],
        "body": textwrap.dedent("""\
            ## Answer
            UUIDv7 is a time-ordered UUID: the first 48 bits are a
            millisecond timestamp. This means inserts are roughly sequential
            in the primary-key index, avoiding the random-page-write problem
            that UUIDv4 causes on B-tree storage.

            For our write-heavy tables (`users`, `events`), UUIDv7 is 2-3x
            faster than UUIDv4 at insert.
            """),
    },
    {
        "title": "Data model: how soft deletes work",
        "summary": "`deleted_at` column; queries default to `WHERE deleted_at IS NULL`; the `with_deleted` scope is opt-in for admin tools.",
        "tags": ["data-model", "soft-delete"],
        "body": textwrap.dedent("""\
            ## Answer
            Every table has a nullable `deleted_at TIMESTAMPTZ` column. The
            ORM scopes all default queries to `deleted_at IS NULL`. Admin
            tools can use the `with_deleted` scope.

            Hard deletes are reserved for GDPR right-to-be-forgotten and
            never for ordinary data cleanup.
            """),
    },
    {
        "title": "Data model: time columns use TIMESTAMPTZ not TIMESTAMP",
        "summary": "All time columns are `TIMESTAMPTZ`; we always store UTC; client-side formatting happens at render time only.",
        "tags": ["data-model", "time"],
        "body": textwrap.dedent("""\
            ## Answer
            `TIMESTAMPTZ` (timestamp with time zone) stores the value
            normalized to UTC internally. We never use plain `TIMESTAMP`
            (without time zone) — those silently drop the offset and
            produce confusing comparisons.
            """),
    },
    {
        "title": "Data model: how monetary amounts are stored",
        "summary": "`BIGINT` storing the smallest currency unit (cents/pence/yen); never `FLOAT` or `NUMERIC` for money; conversion happens at API boundaries.",
        "tags": ["data-model", "money"],
        "body": textwrap.dedent("""\
            ## Answer
            Amounts are `BIGINT` representing the smallest currency unit
            (cents, pence, yen, etc.). The column's currency is named
            `<amount>_<currency>` (e.g., `amount_usd_cents`).

            ## Don't
            Don't use `NUMERIC` or `FLOAT` for money. Float gives you
            wrong answers; numeric is fine but slower and harder to work
            with in client SDKs.
            """),
    },
    {
        "title": "Data model: why we don't use foreign key constraints",
        "summary": "We enforce referential integrity at the application layer because delete-then-cascade order matters across services; FKs would lock too aggressively.",
        "tags": ["data-model", "integrity"],
        "body": textwrap.dedent("""\
            ## Answer
            Foreign keys would force cascading deletes to lock in the
            wrong order across services. We enforce the integrity in the
            application layer, where we can control the order.

            The tradeoff: occasional orphaned rows during partial
            failures. We have a daily `orphan-check` job to detect them.
            """),
    },
]

# ---------------------------------------------------------------------------
# papers/ domain — claim-pages from real ML/systems papers
# ---------------------------------------------------------------------------
#
# Each "paper" contributes 5-8 individual claim pages with `source` set to a
# real DOI or arxiv URL.

PAPER_CLAIMS = {
    "Attention Is All You Need (Vaswani et al., 2017)": [
        {
            "title": "Transformer: scaled dot-product attention definition",
            "summary": "Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V; the sqrt(d_k) scaling prevents softmax saturation when d_k is large.",
            "tags": ["transformer", "attention", "formula"],
            "body": "## Answer\n`Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V`\n\nThe `1/sqrt(d_k)` factor is critical — without it, large `d_k` pushes the softmax into saturated regions with tiny gradients.\n",
            "source": "https://arxiv.org/abs/1706.03762",
        },
        {
            "title": "Transformer: multi-head attention lets the model attend to different representation subspaces",
            "summary": "h parallel attention heads run in parallel; outputs are concatenated and projected; 8 heads in the base model.",
            "tags": ["transformer", "multi-head"],
            "body": "## Answer\n`MultiHead(Q,K,V) = Concat(head_1,...,head_h) W^O`\nwhere `head_i = Attention(QW_i^Q, KW_i^K, VW_i^V)`.\n\nThe base model uses h=8. This lets each head attend to a different representation subspace.",
            "source": "https://arxiv.org/abs/1706.03762",
        },
        {
            "title": "Transformer: positional encoding uses sinusoids",
            "summary": "PE(pos, 2i) = sin(pos / 10000^(2i/d_model)); PE(pos, 2i+1) = cos(...); allows the model to extrapolate to sequence lengths beyond training.",
            "tags": ["transformer", "positional-encoding"],
            "body": "## Answer\nSinusoidal positional encodings:\n```\nPE(pos, 2i) = sin(pos / 10000^(2i/d_model))\nPE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))\n```\nThe authors hypothesized this would help with extrapolation to longer sequences (a property later shown to be weaker than hoped).",
            "source": "https://arxiv.org/abs/1706.03762",
        },
        {
            "title": "Transformer: training took 12 hours on 8 P100 GPUs for the base model",
            "summary": "Base model: ~65M params, 12h on 8 P100 GPUs (the paper's Table 3); big model was ~213M params and took 3.5 days.",
            "tags": ["transformer", "training", "compute"],
            "body": "## Answer\nBase model: ~12 hours on 8 P100 GPUs.\nBig model: ~3.5 days on 8 P100 GPUs.\n\nThese numbers are useful as a sanity check for reproduction — modern reproductions with bigger GPUs finish much faster but the original compute was modest by 2026 standards.",
            "source": "https://arxiv.org/abs/1706.03762",
        },
        {
            "title": "Transformer: BLEU gains on WMT 2014 EN-DE were +2.0 over the prior SOTA",
            "summary": "28.4 BLEU on WMT 2014 EN-DE vs prior SOTA of 26.4 (GNMT ensemble); EN-FR was 41.0 vs prior 40.4.",
            "tags": ["transformer", "results", "translation"],
            "body": "## Answer\nWMT 2014 EN-DE: 28.4 BLEU (prior SOTA 26.4).\nWMT 2014 EN-FR: 41.0 BLEU (prior SOTA 40.4, ByteNet).\n\nThe +2.0 BLEU on EN-DE was the headline result; the smaller +0.6 on EN-FR is what initially convinced skeptics.",
            "source": "https://arxiv.org/abs/1706.03762",
        },
    ],
    "BERT (Devlin et al., 2018)": [
        {
            "title": "BERT: bidirectional pretraining via masked language modeling",
            "summary": "15% of tokens are masked; of those, 80% become [MASK], 10% random token, 10% unchanged; the model predicts the original.",
            "tags": ["bert", "mlm", "pretraining"],
            "body": "## Answer\nMasked Language Modeling (MLM) with a 15% mask rate. Of the masked tokens:\n- 80% → [MASK]\n- 10% → random token\n- 10% → unchanged\n\nThe random/unchanged fractions prevent the model from learning that masked tokens always map to [MASK] at fine-tuning.",
            "source": "https://arxiv.org/abs/1810.04805",
        },
        {
            "title": "BERT: next sentence prediction (NSP) was later shown to be mostly useless",
            "summary": "NSP head contributed little to downstream performance; subsequent work (RoBERTa, ALBERT) dropped it with no loss.",
            "tags": ["bert", "nsp", "design-choice"],
            "body": "## Answer\nNSP was a 50/50 binary classification task predicting whether sentence B follows sentence A in the corpus.\n\nSubsequent work (RoBERTa, 2019) showed NSP contributes little; removing it doesn't hurt and sometimes helps. ALBERT went further with sentence-order prediction (SOP).\n\n## Don't\nDon't cite BERT's NSP results as load-bearing — the field moved on.",
            "source": "https://arxiv.org/abs/1810.04805",
        },
        {
            "title": "BERT: 110M parameters for BERT-base, 340M for BERT-large",
            "summary": "BERT-base: L=12, H=768, A=12, 110M params. BERT-large: L=24, H=1024, A=16, 340M params.",
            "tags": ["bert", "size"],
            "body": "## Answer\nBERT-base: L=12 layers, H=768 hidden, A=12 heads, 110M params.\nBERT-large: L=24, H=1024, A=16, 340M params.\n\nThese configurations are reference points — many later models (RoBERTa, DistilBERT, ALBERT) are scaled variants of one or the other.",
            "source": "https://arxiv.org/abs/1810.04805",
        },
        {
            "title": "BERT: pretrained on 3.3B word tokens (BookCorpus + English Wikipedia)",
            "summary": "Total pretraining corpus: ~3.3B WordPiece tokens; 800M from BooksCorpus, 2.5B from English Wikipedia (whole-word lowercased).",
            "tags": ["bert", "pretraining", "data"],
            "body": "## Answer\nCorpus: BooksCorpus (800M words) + English Wikipedia (2.5B words).\nTotal: ~3.3B WordPiece tokens after preprocessing.\n\nBy 2026 standards this is a small corpus; modern LLMs use orders of magnitude more.",
            "source": "https://arxiv.org/abs/1810.04805",
        },
    ],
    "ResNet (He et al., 2015)": [
        {
            "title": "ResNet: residual connections let networks of 100+ layers train",
            "summary": "y = F(x) + x; the skip connection makes the residual F(x) easier to optimize than the unreferenced mapping; enabled 152-layer ImageNet models.",
            "tags": ["resnet", "skip-connection", "depth"],
            "body": "## Answer\nResidual block: `y = F(x, {W_i}) + x`, where `F` is the convolutional stack.\n\nThe skip connection means that if the optimal transformation is the identity, the network only needs to learn `F(x) = 0` — a much easier optimization target.\n\nThis was the breakthrough that enabled training 152-layer networks (8x deeper than VGG-19) without degradation.",
            "source": "https://arxiv.org/abs/1512.03385",
        },
        {
            "title": "ResNet: 3.57% error on ImageNet (ILSVRC 2015 classification)",
            "summary": "ResNet-152 ensemble: 3.57% top-5 error on ImageNet test set; won ILSVRC 2015 classification.",
            "tags": ["resnet", "results", "imagenet"],
            "body": "## Answer\nResNet-152 ensemble: 3.57% top-5 error on ImageNet test set, winning ILSVRC 2015.\n\nSingle-model ResNet-152: 4.49% top-5 error.\n\nThe 3.57% is an ensemble of 6 models with different depths.",
            "source": "https://arxiv.org/abs/1512.03385",
        },
        {
            "title": "ResNet: shortcut connections can be identity or projection",
            "summary": "Identity shortcuts when dimensions match; projection shortcuts (1x1 conv) when dimensions change; identity works in practice for most layers.",
            "tags": ["resnet", "architecture"],
            "body": "## Answer\nTwo shortcut types:\n- **Identity shortcut**: `y = F(x) + x`. Used when `F`'s output has the same dimensions as `x`.\n- **Projection shortcut**: `y = F(x) + W_s x` where `W_s` is a 1x1 conv. Used when dimensions change (stride 2 downsampling).\n\nThe paper notes identity shortcuts are sufficient in practice for most layers; projection shortcuts add parameters without much accuracy gain.",
            "source": "https://arxiv.org/abs/1512.03385",
        },
        {
            "title": "ResNet: bottleneck blocks reduce compute in deeper variants",
            "summary": "Bottleneck: 1x1 conv (channel reduction) → 3x3 conv → 1x1 conv (channel restoration); ResNet-50/101/152 use this; ResNet-18/34 use basic blocks.",
            "tags": ["resnet", "bottleneck"],
            "body": "## Answer\nBottleneck block: `1x1 conv (channel/4) → 3x3 conv → 1x1 conv (channel)`.\n\nUsed in ResNet-50/101/152 to keep compute reasonable.\nResNet-18/34 use the simpler `3x3 → 3x3` basic block.\n\nThe 1x1 → 3x3 → 1x1 pattern was popularized here and reused in many later architectures.",
            "source": "https://arxiv.org/abs/1512.03385",
        },
    ],
    "Adam Optimizer (Kingma & Ba, 2014)": [
        {
            "title": "Adam: adaptive moments combine momentum and RMSProp",
            "summary": "First moment m_t = EMA of gradients (momentum-like); second moment v_t = EMA of squared gradients (RMSProp-like); bias-corrected; default betas = 0.9, 0.999.",
            "tags": ["adam", "optimizer", "training"],
            "body": "## Answer\nAdam maintains two moving averages:\n- `m_t = β1 * m_{t-1} + (1 - β1) * g_t` (first moment, like momentum)\n- `v_t = β2 * v_{t-1} + (1 - β2) * g_t^2` (second moment, like RMSProp)\n\nBias correction: `m_hat = m_t / (1 - β1^t)`, `v_hat = v_t / (1 - β2^t)`.\n\nUpdate: `θ_t = θ_{t-1} - α * m_hat / (sqrt(v_hat) + ε)`.\n\nDefaults: `β1=0.9`, `β2=0.999`, `ε=1e-8`.",
            "source": "https://arxiv.org/abs/1412.6980",
        },
        {
            "title": "Adam: default learning rate is 1e-3 (much higher than SGD's 1e-2 batch-size-scaled)",
            "summary": "Adam's per-parameter adaptive scaling means the global LR is interpretable; 1e-3 is a good starting point; SGD typically uses 1e-1 with momentum.",
            "tags": ["adam", "learning-rate"],
            "body": "## Answer\nAdam's default LR (1e-3) is roughly an order of magnitude lower than SGD-with-momentum's typical LR (1e-1).\n\nThis is because Adam's per-parameter scaling absorbs part of what the global LR does in SGD.\n\nWhen switching optimizers, scale LR appropriately.",
            "source": "https://arxiv.org/abs/1412.6980",
        },
        {
            "title": "Adam: epsilon in the denominator prevents division by zero",
            "summary": "`1e-8` is the default `eps`; adding it inside the sqrt avoids NaN when v_hat has zeros; larger eps dampens the update step.",
            "tags": ["adam", "epsilon"],
            "body": "## Answer\n`ε` (epsilon) appears in the denominator: `θ_t = θ_{t-1} - α * m_hat / (sqrt(v_hat) + ε)`.\n\nDefault `ε = 1e-8`. Larger values (e.g., `1e-6`) dampen the update for small-v_hat parameters and can improve stability for some tasks.",
            "source": "https://arxiv.org/abs/1412.6980",
        },
        {
            "title": "Adam: weight decay should be decoupled (AdamW) for best results",
            "summary": "L2 regularization in Adam interacts with the adaptive step size; decoupled weight decay (AdamW, Loshchilov & Hutter 2019) treats weight decay separately from the gradient.",
            "tags": ["adam", "adamw", "regularization"],
            "body": "## Answer\nOriginal Adam applies L2 regularization by adding it to the gradient. With Adam's adaptive step size, this regularization is *scaled* by `1/sqrt(v_hat)`, producing non-uniform shrinkage across parameters.\n\nAdamW (Loshchilov & Hutter, 2019) decouples weight decay: `θ_t = θ_{t-1} - α * m_hat / (sqrt(v_hat) + ε) - α * λ * θ_{t-1}`.\n\nThis gives uniform shrinkage. AdamW is the default in essentially all modern transformer training.",
            "source": "https://arxiv.org/abs/1711.05101",
        },
    ],
    "FlashAttention (Dao et al., 2022)": [
        {
            "title": "FlashAttention: IO-aware exact attention via tiling",
            "summary": "Computes attention without materializing the N×N attention matrix in HBM; tiles the softmax into blocks that fit in SRAM; exact, not approximate.",
            "tags": ["flashattention", "memory", "kernel"],
            "body": "## Answer\nStandard attention materializes the `N×N` attention matrix in HBM (`O(N^2)` memory).\n\nFlashAttention tiles the computation: process blocks of Q,K,V that fit in SRAM, compute partial softmax, accumulate output, write final result.\n\nThe result is *exact* (not low-rank approximation), but `O(N)` HBM access instead of `O(N^2)`.\n\nThis gives 2-4x wallclock speedup and ~10x memory reduction for long contexts.",
            "source": "https://arxiv.org/abs/2205.14135",
        },
        {
            "title": "FlashAttention: online softmax trick handles block-wise computation",
            "summary": "Standard softmax needs the full row to compute the denominator; FlashAttention tracks running max and sum so partial blocks can be rescaled correctly.",
            "tags": ["flashattention", "softmax", "numerics"],
            "body": "## Answer\nStandard softmax: `softmax(x_i) = exp(x_i) / Σ exp(x_j)` — needs the full row.\n\nOnline softmax (Milakov & Gimelshein, 2018) tracks:\n- `m_i = max(m_{i-1}, x_i)`\n- `ℓ_i = ℓ_{i-1} * exp(m_{i-1} - m_i) + exp(x_i - m_i)`\n\nThe accumulated max and sum let you rescale partial outputs correctly when new blocks arrive. FlashAttention uses this to compute the tiled softmax without ever holding the full matrix.",
            "source": "https://arxiv.org/abs/2205.14135",
        },
        {
            "title": "FlashAttention: requires GPU SRAM and CUDA; not portable",
            "summary": "FlashAttention is GPU-specific (NVIDIA initially; AMD support came later); CPU/Apple Silicon versions exist but with smaller speedups.",
            "tags": ["flashattention", "hardware"],
            "body": "## Answer\nFlashAttention v1/v2 require NVIDIA GPUs (now AMD ROCm too, with some caveats). The kernel is hand-written CUDA relying on SRAM size and warp scheduling.\n\nApple Silicon and CPU backends exist but the speedup is smaller because the SRAM/HBM gap is less dramatic.",
            "source": "https://arxiv.org/abs/2205.14135",
        },
    ],
    "LoRA (Hu et al., 2021)": [
        {
            "title": "LoRA: low-rank decomposition of weight updates freezes W, trains A and B",
            "summary": "ΔW = BA where B ∈ R^(d×r), A ∈ R^(r×k), r << min(d,k); only A and B are trained; the original W is frozen and merged back at inference.",
            "tags": ["lora", "peft", "training"],
            "body": "## Answer\nFor a pretrained weight matrix `W_0 ∈ R^(d×k)`, LoRA constrains the update to:\n`W = W_0 + ΔW = W_0 + (B @ A)` where `B ∈ R^(d×r)`, `A ∈ R^(r×k)`, `r << min(d,k)`.\n\nOnly A and B receive gradients. At inference, `W = W_0 + B@A` is computed once and merged back into the original matrix — no latency overhead.\n\nTypical `r` values: 4, 8, 16, 32.",
            "source": "https://arxiv.org/abs/2106.09685",
        },
        {
            "title": "LoRA: rank r=8 captures most of the fine-tuning quality",
            "summary": "Empirically, r=4-16 is enough for most tasks; very large r doesn't help much but does increase parameter count.",
            "tags": ["lora", "rank", "hyperparameter"],
            "body": "## Answer\nThe original paper shows that rank 4-16 captures most of the fine-tuning quality for tasks like WikiSQL and MNLI-matched.\n\nRank 64+ gives diminishing returns. Going higher than 64 essentially defeats the purpose.\n\n## Don't\nDon't blindly use r=64 — start at r=8, increase only if quality is insufficient.",
            "source": "https://arxiv.org/abs/2106.09685",
        },
        {
            "title": "LoRA: adapters can be merged into the base model for zero-latency inference",
            "summary": "After training, `W_new = W_0 + B@A`; merged once into the model weights; inference has no adapter overhead.",
            "tags": ["lora", "inference"],
            "body": "## Answer\nAfter training, the merge is:\n```python\nW_0.data += B @ A\n```\n\nThis produces a model with the LoRA adaptation baked in — same forward-pass latency and memory as the base model.\n\n## Don't\nDon't keep adapters separate at inference time if you can merge them. Merging saves the dispatch overhead.",
            "source": "https://arxiv.org/abs/2106.09685",
        },
    ],
    "Dropout (Srivastava et al., 2014)": [
        {
            "title": "Dropout: randomly zero units during training to prevent co-adaptation",
            "summary": "Each forward pass zeros each unit with probability p (typically 0.5 for hidden, 0.1 for input); at test time, no dropout, weights scaled by (1-p) or invert at training.",
            "tags": ["dropout", "regularization"],
            "body": "## Answer\nDuring training: each unit is kept with probability `p` (commonly 0.5 for hidden layers, 0.8–0.9 for input).\n\nDuring inference: all units are active, with weights scaled by `p` (or equivalently, training scales activations by `1/p` — \"inverted dropout\").\n\nThis prevents co-adaptation of features. Srivastava et al. show consistent gains across vision, speech, and NLP tasks.",
            "source": "https://www.jmlr.org/papers/v15/srivastava14a.html",
        },
        {
            "title": "Dropout: acts as an ensemble of exponentially many thinned networks",
            "summary": "Each training pass uses a different sub-network of the original; at test time the full network approximates the ensemble's predictions.",
            "tags": ["dropout", "theory"],
            "body": "## Answer\nWith n units and dropout probability p, each forward pass uses one of `2^n` possible sub-networks.\n\nSrivastava et al. argue this is similar to model averaging / ensemble: training on 2^n thinned networks and using the full network at test time approximates the geometric mean of predictions across the ensemble.",
            "source": "https://www.jmlr.org/papers/v15/srivastava14a.html",
        },
    ],
    "Word2Vec (Mikolov et al., 2013)": [
        {
            "title": "Word2Vec: skip-gram predicts context words from a center word",
            "summary": "Given a center word, predict context words within a window; negative sampling uses ~5-20 noise words instead of full softmax for efficiency.",
            "tags": ["word2vec", "embedding", "training"],
            "body": "## Answer\nSkip-gram with negative sampling (SGNS):\n- Slide a window over the corpus.\n- For each (center, context) pair, train the model to predict `context` from `center`.\n- Use negative sampling: for each positive pair, draw k=5–20 random \"noise\" words and train the model to score them lower.\n\nNegative sampling turns the softmax into a binary classification problem, which is ~1000x faster.",
            "source": "https://arxiv.org/abs/1301.3781",
        },
        {
            "title": "Word2Vec: classic analogy example `king - man + woman ≈ queen`",
            "summary": "Linear algebra on embeddings reproduces semantic relationships; the famous example comes from the original paper and the subsequent tooling.",
            "tags": ["word2vec", "analogy"],
            "body": "## Answer\n`vec(king) - vec(man) + vec(woman) ≈ vec(queen)`\n\nThis works for many semantic relationships (gender, country-capital, verb tense) but not all — and the effect degrades for rare words.\n\nIt is the iconic demonstration that word embeddings encode linear structure.",
            "source": "https://arxiv.org/abs/1301.3781",
        },
        {
            "title": "Word2Vec: embedding dimension is a hyperparameter; typical values 50–300",
            "summary": "Paper used 300 for the 6B token Google News model; smaller dim (50-100) is often enough for downstream tasks and trains faster.",
            "tags": ["word2vec", "dimension"],
            "body": "## Answer\nEmbedding dimension d is a free hyperparameter.\n\nOriginal paper used d=300 for the 6B token Google News model.\nSmaller d (50-100) often works fine for downstream tasks and trains ~3x faster.\n\n## Don't\nDon't assume larger is always better — overfitting becomes a problem at small corpus sizes.",
            "source": "https://arxiv.org/abs/1301.3781",
        },
    ],
    "DQN (Mnih et al., 2015)": [
        {
            "title": "DQN: deep Q-network with experience replay and target network",
            "summary": "Two tricks stabilize Q-learning with neural networks: (1) experience replay buffer breaks temporal correlation; (2) target network updates slowly to stabilize the bootstrap target.",
            "tags": ["dqn", "rl", "stability"],
            "body": "## Answer\nTwo stability tricks:\n\n1. **Experience replay**: store transitions in a buffer; sample uniformly when training. Breaks temporal correlation between consecutive samples.\n\n2. **Target network**: keep a separate Q-network whose parameters are updated only every C steps. The bootstrap target uses this target network, not the live one. Prevents the moving-target problem.",
            "source": "https://www.nature.com/articles/nature14236",
        },
        {
            "title": "DQN: outperformed a professional human player on 49 Atari games",
            "summary": "Out of 49 Atari games tested, DQN exceeded expert human performance on 43; same architecture, same hyperparameters, raw pixels as input.",
            "tags": ["dqn", "results", "atari"],
            "body": "## Answer\nDQN was tested on 49 Atari 2600 games from the Arcade Learning Environment, with the same architecture and hyperparameters across all games (raw pixels + game score as input).\n\nResult: 43/49 games exceeded expert human performance; 6/49 did not (Montezuma's Revenge is the famous failure case).\n\nThe cross-game generality of one architecture is the headline result.",
            "source": "https://www.nature.com/articles/nature14236",
        },
        {
            "title": "DQN: rewards clipped to {-1, 0, +1} to handle different game score scales",
            "summary": "Sign of reward, not magnitude; allows one set of hyperparameters to work across games with wildly different raw scores (Pong: +/-1; Ms. Pac-Man: thousands).",
            "tags": ["dqn", "reward-clipping"],
            "body": "## Answer\nReward clipping: positive reward becomes +1, negative becomes -1, zero stays 0.\n\nThis normalizes the reward scale across games. Without clipping, gradient magnitudes would vary wildly between games (e.g., Pong: +/-1 reward vs. Ms. Pac-Man: thousands).\n\nThis is one of the tricks that makes the cross-game single-hyperparameter setup work.",
            "source": "https://www.nature.com/articles/nature14236",
        },
    ],
    "PPO (Schulman et al., 2017)": [
        {
            "title": "PPO: clipped surrogate objective prevents destructively large policy updates",
            "summary": "ratio = exp(new_logp - old_logp); objective = min(ratio * advantage, clip(ratio, 1-eps, 1+eps) * advantage); eps=0.2 default.",
            "tags": ["ppo", "rl", "policy-gradient"],
            "body": "## Answer\nPPO's clipped objective:\n\n```\nratio = exp(log_prob_new - log_prob_old)\nobjective = min(ratio * advantage,\n                clip(ratio, 1 - eps, 1 + eps) * advantage)\n```\n\nThe `clip` term removes incentive to move `ratio` outside `[1-eps, 1+eps]`, keeping updates close to the old policy. Default `eps = 0.2`.\n\nThis is simpler than TRPO (which uses a KL constraint with a Hessian) and empirically comparable in performance.",
            "source": "https://arxiv.org/abs/1707.06347",
        },
        {
            "title": "PPO: the de facto RL algorithm for continuous and discrete control tasks",
            "summary": "First-choice algorithm for most RLHF, robotics, and game-playing setups; robust across hyperparameter settings; easy to implement.",
            "tags": ["ppo", "rl", "default"],
            "body": "## Answer\nPPO is widely treated as the default policy-gradient algorithm:\n- Robust across hyperparameters (compared to A2C, TRPO).\n- Implementable in ~100 lines (compared to TRPO's constrained optimization).\n- Works on continuous and discrete action spaces.\n\nUsed in: RLHF (InstructGPT, early ChatGPT), robotics (OpenAI's Dactyl), game AI (Dota 2 Five).",
            "source": "https://arxiv.org/abs/1707.06347",
        },
        {
            "title": "PPO: clipping epsilon controls how far the new policy can drift",
            "summary": "epsilon=0.2 in the original paper; lower epsilon (0.1) for more conservative updates; higher (0.3) for faster but riskier updates.",
            "tags": ["ppo", "hyperparameter"],
            "body": "## Answer\nepsilon in the PPO clip controls trust-region size:\n- 0.1: conservative, more updates needed.\n- 0.2: paper default, robust across tasks.\n- 0.3: aggressive, faster learning on stable tasks, less robust.\n\nDon't tune this before tuning the learning rate. LR matters more.",
            "source": "https://arxiv.org/abs/1707.06347",
        },
    ],
    "VAE (Kingma & Welling, 2013)": [
        {
            "title": "VAE: encoder-decoder with a probabilistic latent space",
            "summary": "Encoder outputs mean and variance of a Gaussian posterior q(z|x); sample z from N(mu, sigma^2); decoder reconstructs x; KL term regularizes q toward N(0, I).",
            "tags": ["vae", "generative", "latent"],
            "body": "## Answer\nVAE training:\n1. Encoder: x -> (mu, log sigma^2) parameters of q(z|x).\n2. Sample z = mu + sigma * eps, with eps ~ N(0, I).\n3. Decoder: p(x|z) reconstructs x.\n4. Loss = -E[log p(x|z)] + KL(q(z|x) || N(0, I)).\n\nThe KL term regularizes the latent space to be close to a standard Gaussian, enabling sampling at generation time.\n\nThe 'reparameterization trick' (sampling eps separately) is what makes the whole thing differentiable.",
            "source": "https://arxiv.org/abs/1312.6114",
        },
        {
            "title": "VAE: reparameterization trick makes sampling differentiable",
            "summary": "z = mu + sigma * eps, with eps ~ N(0, I); sampling eps outside the gradient path lets gradients flow through mu and sigma.",
            "tags": ["vae", "reparameterization"],
            "body": "## Answer\nWithout the reparameterization trick, sampling z ~ N(mu, sigma^2) inside the forward pass would block gradient flow (the sampling op isn't differentiable).\n\nThe trick: `z = mu + sigma * eps` where `eps ~ N(0, I)`. The randomness is now in eps, which is treated as a constant during backprop. Gradients flow through mu and sigma normally.",
            "source": "https://arxiv.org/abs/1312.6114",
        },
        {
            "title": "VAE: ELBO is the lower bound on log-likelihood being maximized",
            "summary": "ELBO = E_q[log p(x|z)] - KL(q(z|x) || p(z)); equivalent to the loss written as reconstruction + KL; the bound is tight when q matches p(z|x).",
            "tags": ["vae", "elbo", "theory"],
            "body": "## Answer\nELBO (Evidence Lower Bound):\n`log p(x) >= E_q(z|x)[log p(x|z)] - KL(q(z|x) || p(z))`\n\nThe training loss is `-ELBO`. Maximizing ELBO maximizes a lower bound on the true log-likelihood. The bound is tight when `q(z|x) = p(z|x)` exactly.",
            "source": "https://arxiv.org/abs/1312.6114",
        },
    ],
    "BatchNorm (Ioffe & Szegedy, 2015)": [
        {
            "title": "BatchNorm: normalize activations per mini-batch during training",
            "summary": "x_hat = (x - mu_B) / sqrt(sigma^2_B + eps); scale and shift: y = gamma * x_hat + beta; mu_B and sigma^2_B are batch statistics; running averages maintained for inference.",
            "tags": ["batchnorm", "normalization", "training"],
            "body": "## Answer\nPer mini-batch:\n1. Compute batch mean `mu_B` and variance `sigma^2_B`.\n2. Normalize: `x_hat = (x - mu_B) / sqrt(sigma^2_B + eps)`.\n3. Scale and shift: `y = gamma * x_hat + beta`.\n\nDuring training, maintain exponential moving averages of `mu_B` and `sigma^2_B` for inference.\n\n## Don't\nDon't apply BatchNorm before the very first layer -- there's no benefit and it can destabilize early training.",
            "source": "https://arxiv.org/abs/1502.03167",
        },
        {
            "title": "BatchNorm: enables higher learning rates and reduces the importance of careful initialization",
            "summary": "By keeping activations normalized, gradients don't explode/vanish as easily, so larger learning rates become safe.",
            "tags": ["batchnorm", "training", "lr"],
            "body": "## Answer\nBatchNorm reduces internal covariate shift (the change in layer input distributions during training). This:\n1. Allows larger learning rates (gradients don't explode).\n2. Reduces sensitivity to weight initialization.\n3. Acts as a mild regularizer.",
            "source": "https://arxiv.org/abs/1502.03167",
        },
    ],
    "GELU (Hendrycks & Gimpel, 2016)": [
        {
            "title": "GELU: Gaussian Error Linear Unit activation used in transformers",
            "summary": "GELU(x) = x * Phi(x) where Phi is the standard normal CDF; smooth approximation of ReLU with non-zero gradient everywhere.",
            "tags": ["gelu", "activation", "transformer"],
            "body": "## Answer\nGELU(x) = x * Phi(x), where Phi is the standard normal CDF.\n\nEquivalent forms:\n- 0.5 * x * (1 + erf(x / sqrt(2)))\n- 0.5x(1 + tanh(sqrt(2/pi) * (x + 0.044715 x^3))) (approximation)\n\nUsed in BERT, GPT, RoBERTa, and most modern transformers. Smoother than ReLU (non-zero gradient for negative inputs) which empirically helps optimization.",
            "source": "https://arxiv.org/abs/1606.08415",
        },
        {
            "title": "GELU: smoother than ReLU; stochastic regularization interpretation",
            "summary": "Can be interpreted as multiplying x by a Bernoulli mask with probability Phi(x); the stochastic view explains why it generalizes better than ReLU.",
            "tags": ["gelu", "activation", "theory"],
            "body": "## Answer\nGELU(x) = x * P(X <= x) where X ~ N(0, 1).\n\nStochastic interpretation: mask x with a Bernoulli random variable that takes value 1 with probability Phi(x). This is a smoother (non-binary) version of dropout-on-the-input.",
            "source": "https://arxiv.org/abs/1606.08415",
        },
    ],
    "YOLO (Redmon et al., 2016)": [
        {
            "title": "YOLO: real-time object detection with a single neural network",
            "summary": "Single CNN predicts bounding boxes and class probabilities for all objects in one forward pass; 45 FPS on Titan X; trades small accuracy for big speed.",
            "tags": ["yolo", "detection", "real-time"],
            "body": "## Answer\nYOLO (You Only Look Once) reframes detection as a single regression problem: one CNN predicts bounding boxes and class probabilities in one forward pass.\n\nSpeed: 45 FPS on a Titan X GPU.\nAccuracy: lower than Faster R-CNN but acceptable for many use cases.\n\n## Don't\nDon't apply YOLO to small-object detection without considering YOLOv3+ variants -- the original struggles with small objects.",
            "source": "https://arxiv.org/abs/1506.02640",
        },
        {
            "title": "YOLO: divides image into SxS grid; each cell predicts B boxes",
            "summary": "Grid-based prediction: each cell is responsible for objects whose center falls in that cell; B=2 default; confidence score is P(object) times IoU.",
            "tags": ["yolo", "architecture"],
            "body": "## Answer\nYOLO architecture:\n1. Divide the image into an SxS grid (default S=7).\n2. Each grid cell predicts B bounding boxes (default B=2).\n3. Each box has: (x, y, w, h, confidence).\n4. Each cell also predicts class probabilities (conditioned on object presence).\n\nTotal output tensor: S x S x (B * 5 + C) where C is the number of classes.",
            "source": "https://arxiv.org/abs/1506.02640",
        },
    ],
    "PER (Schaul et al., 2016)": [
        {
            "title": "PER: prioritize replay buffer samples by TD error magnitude",
            "summary": "Sample transitions with probability proportional to |TD error|; high-error (i.e. surprising) transitions are sampled more often; importance-sampling weights correct the bias.",
            "tags": ["per", "dqn", "replay-buffer"],
            "body": "## Answer\nPrioritized Experience Replay:\n- Each transition stored with priority `p_i = |TD error| + eps`.\n- Sampling probability `P(i) = p_i^alpha / Sigma p_k^alpha` (alpha=0.6 typical).\n- Importance-sampling weight `w_i = (N * P(i))^(-beta)` corrects the bias introduced by non-uniform sampling (beta anneals from 0.4 to 1.0).\n\nResult: 2x faster learning on most Atari games compared to uniform sampling.",
            "source": "https://arxiv.org/abs/1511.05952",
        },
        {
            "title": "PER: rank-based vs proportional prioritization",
            "summary": "Two variants: rank-based uses the rank in |TD error| order (robust to outliers); proportional uses raw |TD error| (faster but sensitive to outliers). Rank-based is more common.",
            "tags": ["per", "variants"],
            "body": "## Answer\nTwo prioritization schemes:\n- **Proportional**: `p_i = |TD_i| + eps`. Sensitive to outlier errors.\n- **Rank-based**: `p_i = 1 / rank(i)` where rank is by |TD error|. More robust.\n\nThe original paper found rank-based slightly better on most Atari games. Most implementations use rank-based by default.",
            "source": "https://arxiv.org/abs/1511.05952",
        },
    ],
    "Distillation (Hinton et al., 2015)": [
        {
            "title": "Knowledge distillation: train a small model to match a large model's soft outputs",
            "summary": "Student is trained on a softmax of the teacher's logits at temperature T > 1; the soft labels carry more information than hard labels.",
            "tags": ["distillation", "training", "compression"],
            "body": "## Answer\nDistillation loss:\n```\nL = alpha * L_hard(student, true_labels) + (1 - alpha) * L_soft(student, teacher)\n```\nwhere `L_soft` uses softmax with temperature `T > 1` (typically T=2-5).\n\nHigher T produces softer probability distributions, which encode inter-class similarities that hard labels miss (e.g., 'this image is 0.7 truck, 0.3 car' rather than just 'truck').",
            "source": "https://arxiv.org/abs/1503.02531",
        },
        {
            "title": "Distillation: temperature T controls softness of probability distribution",
            "summary": "Softmax(x/T) with T=1 is the standard softmax; T>1 flattens the distribution, exposing dark knowledge; T<1 sharpens it.",
            "tags": ["distillation", "temperature"],
            "body": "## Answer\nTemperature scaling: `softmax(x/T)`.\n- T=1: standard softmax.\n- T>1: softer distribution (more uniform); reveals dark knowledge.\n- T<1: sharper distribution (peaks amplified).\n\nFor distillation, T=2 to T=5 is typical. At inference, the student uses T=1.",
            "source": "https://arxiv.org/abs/1503.02531",
        },
        {
            "title": "Distillation: why soft labels encode more than hard labels",
            "summary": "A 0.7 truck / 0.3 car distribution encodes similarity to other classes; a 1.0 truck hard label doesn't; the student learns relationships, not just categories.",
            "tags": ["distillation", "theory"],
            "body": "## Answer\nHinton et al.'s 'dark knowledge' insight: the teacher's soft probability distribution encodes inter-class similarities that hard labels miss.\n\nExample: a car and a truck share visual features. Hard labels say 'truck' (1.0, 0.0). Soft labels say 'truck 0.7, car 0.2, vehicle 0.1'. The student learns 'trucks look like cars' from the second case, not the first.\n\nThis is why distillation can outperform training on the original labels.",
            "source": "https://arxiv.org/abs/1503.02531",
        },
    ],
    "GAN (Goodfellow et al., 2014)": [
        {
            "title": "GAN: two networks trained in opposition -- generator and discriminator",
            "summary": "G generates fake samples from noise; D tries to distinguish real from fake; G is trained to fool D; minimax objective; alternating updates.",
            "tags": ["gan", "generative", "adversarial"],
            "body": "## Answer\nTwo networks:\n- **Generator G**: maps noise z ~ p(z) to a sample G(z) in data space.\n- **Discriminator D**: outputs P(real | x).\n\nMinimax objective:\n`min_G max_D E[log D(x)] + E[log(1 - D(G(z)))]`\n\nIn practice, G is trained to maximize `log D(G(z))` (the non-saturating variant) because the original objective's gradient vanishes early in training.",
            "source": "https://arxiv.org/abs/1406.2661",
        },
        {
            "title": "GAN: training is unstable and prone to mode collapse",
            "summary": "Mode collapse: G produces the same output regardless of z; G and D oscillate without convergence; many practical tricks (spectral norm, two-timescale updates) needed for stability.",
            "tags": ["gan", "training", "stability"],
            "body": "## Answer\nClassic GAN training problems:\n- **Mode collapse**: G learns to produce one realistic output regardless of z.\n- **Oscillation**: G and D chase each other without settling.\n- **Vanishing gradients**: when D is too good, G's signal disappears.\n\nStabilization tricks (introduced after the original paper):\n- Two-timescale learning rates (D faster than G).\n- Spectral normalization on D.\n- Gradient penalty (WGAN-GP).\n- Minibatch discrimination.",
            "source": "https://arxiv.org/abs/1406.2661",
        },
        {
            "title": "GAN: Wasserstein distance formulation gives more stable training (WGAN)",
            "summary": "WGAN replaces JS divergence with Earth Mover's distance; critic (no sigmoid) outputs unbounded scores; gradient penalty enforces Lipschitz constraint.",
            "tags": ["gan", "wgan", "training"],
            "body": "## Answer\nWasserstein GAN (Arjovsky et al., 2017): replace the JS divergence in the original GAN objective with the Wasserstein-1 (Earth Mover's) distance.\n\nKey changes:\n- Critic (not discriminator) outputs unbounded scores.\n- Weight clipping or gradient penalty enforces the 1-Lipschitz constraint.\n- Loss correlates with sample quality, unlike the original GAN loss.\n\nThis makes training dynamics much more interpretable.",
            "source": "https://arxiv.org/abs/1701.07875",
        },
    ],
    "LayerNorm (Ba et al., 2016)": [
        {
            "title": "LayerNorm: normalize across features within each example",
            "summary": "Unlike BatchNorm, LayerNorm computes mean/variance per-example across the feature dimension; no batch dependency; works with variable batch sizes and RNNs.",
            "tags": ["layernorm", "normalization", "transformer"],
            "body": "## Answer\nLayerNorm normalizes across the feature dimension for each example independently:\n```\nmu = mean(x, dim=features)\nsigma = std(x, dim=features)\nx_hat = (x - mu) / (sigma + eps)\ny = gamma * x_hat + beta\n```\n\nNo batch statistics are needed. This makes LayerNorm work in:\n- Variable batch sizes (including batch=1).\n- RNNs (where batch statistics are awkward).\n- Transformers (where it became the default).",
            "source": "https://arxiv.org/abs/1607.06450",
        },
        {
            "title": "LayerNorm vs BatchNorm: which to use when",
            "summary": "BatchNorm: CNNs, fixed batch sizes, faster training. LayerNorm: transformers, RNNs, variable batch sizes, distributed training.",
            "tags": ["layernorm", "batchnorm", "comparison"],
            "body": "## Answer\nRule of thumb:\n- **BatchNorm**: convolutional networks with large fixed batch sizes; benefits from batch noise as regularization.\n- **LayerNorm**: transformers (BERT, GPT, etc.), RNNs, anywhere batch statistics are awkward or vary.\n\nMost NLP models use LayerNorm exclusively. Most vision CNNs (without transformers) use BatchNorm.\n\n## Don't\nDon't mix BatchNorm and LayerNorm in the same model without thinking it through -- they interact with optimizer settings differently.",
            "source": "https://arxiv.org/abs/1607.06450",
        },
    ],
    "RMSNorm (Zhang & Sennrich, 2019)": [
        {
            "title": "RMSNorm: layer norm without the mean-centering step",
            "summary": "Only the root-mean-square scaling is applied; no mean subtraction; saves compute; matches LayerNorm quality on most transformer tasks.",
            "tags": ["rmsnorm", "normalization", "transformer"],
            "body": "## Answer\nRMSNorm:\n```\nrms = sqrt(mean(x^2) + eps)\nx_hat = x / rms\ny = gamma * x_hat\n```\n\nNo mean subtraction, no learned beta. Empirically matches LayerNorm on most transformer benchmarks with ~10-15% less compute.\n\nUsed in LLaMA, Gemma, and most modern open-weight LLMs.",
            "source": "https://arxiv.org/abs/1910.07467",
        },
        {
            "title": "RMSNorm: why dropping mean-centering works",
            "summary": "The re-centering operation has minimal effect because the subsequent linear layer can absorb any constant offset; the re-scaling is what actually stabilizes training.",
            "tags": ["rmsnorm", "theory"],
            "body": "## Answer\nLayerNorm's re-centering step shifts activations to zero mean. But:\n- The next linear layer (y = Wx + b) absorbs any constant offset via its bias b.\n- The re-scaling (dividing by std) is what stabilizes training by controlling activation magnitudes.\n\nEmpirically, dropping the mean subtraction loses ~0% accuracy on most benchmarks while saving compute. The paper argues the rescaling is the load-bearing part.",
            "source": "https://arxiv.org/abs/1910.07467",
        },
    ],
    "Mixture of Experts (Shazeer et al., 2017)": [
        {
            "title": "Sparse MoE: route each token to top-k experts out of N total",
            "summary": "Router network produces N logits; top-k are selected (typically k=2); only those experts process the token; total compute stays low while parameter count grows.",
            "tags": ["moe", "sparse", "transformer"],
            "body": "## Answer\nSparse Mixture of Experts:\n- N expert FFN sub-networks (e.g., N=8 to 64).\n- Router computes logits for each expert per token.\n- Top-k experts (typically k=2) process each token.\n- Output is a weighted sum of the selected experts' outputs.\n\nTotal parameters grow with N, but compute per token stays roughly constant. This is how Mixtral 8x7B has ~47B params but compute similar to ~13B dense.",
            "source": "https://arxiv.org/abs/1701.06538",
        },
        {
            "title": "MoE: load balancing loss prevents expert collapse",
            "summary": "Auxiliary loss penalizes uneven routing across experts; without it, the router converges to sending all tokens to a few experts (collapse).",
            "tags": ["moe", "load-balancing", "training"],
            "body": "## Answer\nWithout balancing, the router learns to favor a few 'good' experts, leaving others unused -- destroying the capacity benefit.\n\nAuxiliary loss (Switch Transformer, Fedus et al., 2022):\n```\nloss_balance = alpha * N * sum(f_i * P_i)\n```\nwhere `f_i` is the fraction of tokens routed to expert i and `P_i` is the average routing probability. Minimized when tokens are uniformly distributed.\n\nTypical `alpha = 0.01`.",
            "source": "https://arxiv.org/abs/2101.03961",
        },
    ],
    "SwiGLU (Shazeer, 2020)": [
        {
            "title": "SwiGLU: gated activation in transformer FFN blocks",
            "summary": "FFN(x) = (W_1 x * sigma(W_gate x)) W_2; the gate controls information flow; SwiGLU uses SiLU (Swish) as the activation; outperforms ReLU/GELU FFN on most benchmarks.",
            "tags": ["swiglu", "activation", "transformer"],
            "body": "## Answer\nGLU (Gated Linear Unit) FFN:\n```\noutput = (W_1 x * sigma(W_gate x)) W_2\n```\n\nSwiGLU (Shazeer, 2020): `sigma` is SiLU/Swish (`x * sigmoid(x)`).\n\nStandard in LLaMA, PaLM, Mistral, and most modern transformer FFNs.\n\nA common variant: 2/3 size for `W_1` and `W_gate` to keep total parameter count constant (compensating for the extra matrix).",
            "source": "https://arxiv.org/abs/2002.05202",
        },
        {
            "title": "SwiGLU: parameter-equivalent vs parameter-matched compared to ReLU/GELU",
            "summary": "Naive SwiGLU adds an extra W_gate matrix (3 matrices vs 2); the common practice is to shrink W_1 and W_gate to 2/3 width so total params stay equal.",
            "tags": ["swiglu", "parameter-count"],
            "body": "## Answer\nParameter accounting:\n- Standard FFN (ReLU/GELU): 2 matrices (W_1, W_2).\n- Naive SwiGLU: 3 matrices (W_1, W_gate, W_2). ~50% more params.\n\nTo match param count: set hidden dim to (8/3 * d_model) instead of 4 * d_model, which makes the 3-matrix count equal the 2-matrix count.\n\nThis is why LLaMA uses hidden_dim = (8/3) * d_model * 2 (the *2 is for SwiGLU) instead of 4 * d_model.",
            "source": "https://arxiv.org/abs/2002.05202",
        },
    ],
    "RoPE (Su et al., 2021)": [
        {
            "title": "RoPE: rotary position embeddings applied to query and key vectors",
            "summary": "Each pair of adjacent dimensions in q and k is rotated by an angle proportional to the position; the rotation matrix depends only on position, not content.",
            "tags": ["rope", "positional-encoding", "transformer"],
            "body": "## Answer\nRoPE rotates q and k vectors by position-dependent angles:\n```\nq_i' = R(m * theta_i) * q_i\nk_i' = R(n * theta_i) * k_i\n```\nwhere m, n are token positions and `theta_i = 10000^(-2i/d)`.\n\nThe key property: `q_i' . k_j'` depends only on `(m - n)`, encoding relative position implicitly.\n\nUsed in LLaMA, Mistral, Gemma, and most modern open-weight LLMs.",
            "source": "https://arxiv.org/abs/2104.09864",
        },
        {
            "title": "RoPE: relative position emerges from absolute rotations",
            "summary": "The dot product of rotated q and k depends only on their relative distance (m - n), not on absolute positions; this gives length extrapolation properties.",
            "tags": ["rope", "theory"],
            "body": "## Answer\nAlgebraic property: for RoPE-rotated vectors q_m and k_n,\n`<q_m, k_n> = f(q, k, m - n)`\n\ni.e., the attention score depends only on the relative position, not on where in the sequence each token sits.\n\nThis implicit relative-position encoding enables length extrapolation better than absolute position embeddings.",
            "source": "https://arxiv.org/abs/2104.09864",
        },
    ],
    "ALiBi (Press et al., 2022)": [
        {
            "title": "ALiBi: attention with linear biases (no position embeddings)",
            "summary": "Adds a non-trainable linear bias `-m * |i - j|` to attention scores; the slope m is fixed per head; no learned position embeddings needed.",
            "tags": ["alibi", "positional-encoding", "transformer"],
            "body": "## Answer\nALiBi modifies attention scores:\n`score(q_i, k_j) = q_i . k_j - m_h * |i - j|`\n\nThe slope `m_h` is a fixed geometric sequence per head (no learning). Recent tokens get less penalty than distant ones, preserving order.\n\nUsed in BLOOM. Strong length extrapolation -- a model trained on 1k tokens can be evaluated on 10k+ with minimal degradation.",
            "source": "https://arxiv.org/abs/2108.12409",
        },
    ],
    "Mamba (Gu & Dao, 2023)": [
        {
            "title": "Mamba: selective state-space model that competes with transformers",
            "summary": "Replaces attention with a selective state-space layer; input-dependent discretization of a continuous-time linear recurrence; linear-time inference; competitive with transformers on language.",
            "tags": ["mamba", "ssm", "architecture"],
            "body": "## Answer\nMamba is a selective state-space model:\n- Continuous-time linear recurrence: `h'(t) = A h(t) + B x(t)`, `y(t) = C h(t)`.\n- Discretized per-step with input-dependent `A`, `B`, `C` (the 'selective' part).\n- Linear-time inference (no quadratic attention).\n- Trained with a hardware-aware parallel scan.\n\nCompetitive with similarly-sized transformers on language modeling and several downstream tasks. The hybrid Mamba+attention (Jamba) is the production form.",
            "source": "https://arxiv.org/abs/2312.00752",
        },
        {
            "title": "Mamba: the selective mechanism makes the recurrence input-dependent",
            "summary": "Unlike S4 (which uses fixed A, B, C), Mamba makes the discretization parameters functions of the input; this lets the model selectively remember or forget.",
            "tags": ["mamba", "ssm", "design"],
            "body": "## Answer\nS4 (predecessor): fixed A, B, C parameters per layer; can't adapt to input.\n\nMamba (improvement): makes B, C, and the discretization step size functions of the input:\n```\nB = W_B * x\nC = W_C * x\ndelta = softplus(W_delta * x)\n```\n\nThis lets the model selectively choose what to keep in state and what to overwrite -- the key capability missing from earlier SSMs.",
            "source": "https://arxiv.org/abs/2312.00752",
        },
    ],
    "DPO (Rafailov et al., 2023)": [
        {
            "title": "DPO: direct preference optimization replaces RLHF's reward model + PPO",
            "summary": "Skip the reward model and the PPO loop; optimize a single classification loss directly on preference pairs (chosen, rejected); simpler, faster, often comparable quality.",
            "tags": ["dpo", "rlhf", "alignment"],
            "body": "## Answer\nDPO loss:\n```\nL = -log_sigmoid(beta * (log_p(chosen|x) - log_p(rejected|x) - log_pref(chosen) + log_pref(rejected)))\n```\n\nSkips the reward model entirely. Just preference pairs `(x, y_w, y_l)` and a reference policy for KL regularization.\n\nEmpirically: matches PPO-based RLHF on many tasks with ~10x less compute and no separate reward model to train.\n\nLimitation: weaker than PPO when high-quality preference data is abundant (RLHF's sample efficiency advantage).",
            "source": "https://arxiv.org/abs/2305.18290",
        },
    ],
    "General ML concepts": [
        {
            "title": "Softmax: turns logits into a probability distribution",
            "summary": "softmax(x_i) = exp(x_i) / Sigma_j exp(x_j); outputs sum to 1; amplifies differences; numerically unstable for large logits (subtract max first).",
            "tags": ["softmax", "activation", "fundamentals"],
            "body": "## Answer\nsoftmax(x_i) = exp(x_i) / sum_j exp(x_j)\n\nProperties:\n- Outputs are non-negative and sum to 1 (a probability distribution).\n- Amplifies differences: large logit differences become near-binary probabilities.\n- Used for multi-class classification output layers and attention weights.\n\nNumerical stability: subtract max before exp to avoid overflow:\n`softmax(x) = exp(x - max(x)) / sum exp(x - max(x))`",
            "source": "https://en.wikipedia.org/wiki/Softmax_function",
        },
        {
            "title": "Cross-entropy loss: negative log-likelihood of the true class",
            "summary": "L = -log(p_true); for one-hot y: L = -sum y_i log(p_i); combined with softmax gives a clean gradient equal to (p - y).",
            "tags": ["cross-entropy", "loss", "fundamentals"],
            "body": "## Answer\nCross-entropy loss:\n`L = -sum_i y_i * log(p_i)`\n\nFor one-hot labels where y_k = 1, this simplifies to:\n`L = -log(p_k)`\n\nWhen combined with softmax as the output activation, the gradient is `p - y` -- the cleanest possible gradient for classification. This is why softmax + cross-entropy is the standard pair.",
            "source": "https://en.wikipedia.org/wiki/Cross-entropy",
        },
        {
            "title": "Temperature in sampling: T<1 sharpens; T>1 flattens",
            "summary": "softmax(logits/T); T=1 is the model's natural distribution; T=0 is argmax (greedy); T>1 is more random; lower T produces more deterministic outputs.",
            "tags": ["sampling", "temperature", "decoding"],
            "body": "## Answer\nSampling temperature T:\n- T = 0: argmax (greedy decoding, fully deterministic).\n- T < 1: sharper distribution (peaks amplified). Use for factual / code.\n- T = 1: model's natural distribution.\n- T > 1: flatter distribution (more random). Use for creative writing.\n\nPractical range: 0.1 to 1.5 for most tasks. T = 0.7 is a common default for chat.",
            "source": "https://arxiv.org/abs/1904.09751",
        },
        {
            "title": "Top-p (nucleus) sampling: sample from smallest set whose probabilities sum to p",
            "summary": "Sort tokens by probability; take the smallest prefix whose cumulative mass >= p; sample uniformly from that set; better than top-k at adapting to distribution shape.",
            "tags": ["sampling", "nucleus", "decoding"],
            "body": "## Answer\nNucleus (top-p) sampling:\n1. Sort tokens by probability descending.\n2. Find the smallest set V whose cumulative probability >= p.\n3. Renormalize and sample from V.\n\np = 0.9 is a common default. Unlike top-k (fixed cutoff), top-p adapts: for sharp distributions V is small; for flat distributions V is large.",
            "source": "https://arxiv.org/abs/1904.09751",
        },
        {
            "title": "Beam search: keep top-k partial hypotheses at each step",
            "summary": "At each decoding step, expand each hypothesis with all next tokens; keep top-k by cumulative log-probability; trades compute for search quality; greedy is beam=1.",
            "tags": ["beam-search", "decoding"],
            "body": "## Answer\nBeam search with beam size k:\n- Start with <bos> as the only hypothesis.\n- At each step: expand each hypothesis with all next tokens.\n- Keep top-k by cumulative log-prob.\n- Stop when all beams hit <eos> or max length.\n\nBeam 1 = greedy. Beam 4-8 is typical for translation. Larger beams give diminishing returns.",
            "source": "https://en.wikipedia.org/wiki/Beam_search",
        },
        {
            "title": "Gradient descent: the basic training loop",
            "summary": "theta <- theta - lr * grad(L(theta)); iterate over mini-batches until convergence; SGD uses one example at a time; mini-batch is a compromise.",
            "tags": ["optimization", "training", "fundamentals"],
            "body": "## Answer\nVanilla gradient descent:\n`theta <- theta - lr * grad(L(theta))`\n\nVariants by batch size:\n- **Batch GD**: full dataset per step. Smooth, slow, memory-heavy.\n- **SGD**: one example per step. Fast, noisy.\n- **Mini-batch GD**: b examples per step (b = 32-512 typical). The default.\n\nThe noise in SGD acts as implicit regularization and helps escape saddle points.",
            "source": "https://en.wikipedia.org/wiki/Gradient_descent",
        },
        {
            "title": "Learning rate: the most important hyperparameter",
            "summary": "Too high: loss oscillates or diverges. Too low: slow convergence, gets stuck. Right: loss decreases smoothly. Default for Adam is 1e-3; for SGD with momentum is 1e-1.",
            "tags": ["learning-rate", "training", "hyperparameter"],
            "body": "## Answer\nThe single most consequential hyperparameter.\n\nSymptoms of wrong LR:\n- Too high: loss spikes, NaN, model diverges.\n- Too low: loss decreases but plateaus before fitting.\n\nDefaults:\n- Adam: 1e-3\n- SGD with momentum: 1e-1\n- LLaMA-style: 3e-4 with cosine schedule\n\nLR schedulers (cosine, linear warmup + decay) almost always beat constant LR.",
            "source": "https://arxiv.org/abs/1506.01186",
        },
        {
            "title": "Weight initialization: Xavier and He (Kaiming)",
            "summary": "Xavier: variance ~ 1/fan_in for tanh/sigmoid. He: variance ~ 2/fan_in for ReLU. Wrong init causes vanishing/exploding gradients.",
            "tags": ["initialization", "training", "fundamentals"],
            "body": "## Answer\nTwo common defaults:\n\n**Xavier (Glorot)**: `Var(W) = 1/fan_in` or `2/(fan_in + fan_out)`. Best for tanh / sigmoid activations.\n\n**He (Kaiming)**: `Var(W) = 2/fan_in`. Best for ReLU / leaky ReLU.\n\nModern transformers typically use smaller init schemes (GPT-2 style: `std = 0.02`) and rely on LayerNorm to control magnitudes.",
            "source": "https://arxiv.org/abs/1502.01852",
        },
        {
            "title": "Tokenization: BPE, WordPiece, and SentencePiece",
            "summary": "Subword tokenization splits rare words into common pieces; BPE iteratively merges frequent pairs; WordPiece uses likelihood-based merges; SentencePiece is language-agnostic.",
            "tags": ["tokenization", "preprocessing"],
            "body": "## Answer\nSubword tokenization addresses the open-vocabulary problem:\n\n- **BPE (Byte Pair Encoding)**: start with characters; iteratively merge the most frequent adjacent pair. Used by GPT.\n- **WordPiece**: like BPE but uses likelihood-weighted merges. Used by BERT.\n- **SentencePiece**: language-agnostic; treats input as raw bytes/unicode. Used by LLaMA.\n\nAll produce a fixed vocabulary (32k-200k tokens) and handle unseen words by splitting.",
            "source": "https://arxiv.org/abs/1508.07909",
        },
        {
            "title": "Tokenization: special tokens and their roles",
            "summary": "<bos>, <eos>, <pad>, <unk>, <mask> mark sequence boundaries, padding, unknown words, and masked positions; each model family has its own vocabulary.",
            "tags": ["tokenization", "preprocessing"],
            "body": "## Answer\nStandard special tokens:\n- `<bos>` / `<s>`: beginning of sequence.\n- `<eos>` / `</s>`: end of sequence. Used for chat to mark turn boundaries.\n- `<pad>`: padding for variable-length batches.\n- `<unk>`: out-of-vocabulary (rarely seen with subword vocab).\n- `<mask>`: masked language modeling (BERT).\n\nEach tokenizer has its own. Always check the tokenizer's special tokens before fine-tuning.",
            "source": "https://huggingface.co/docs/transformers/tokenizer_summary",
        },
        {
            "title": "BLEU score: n-gram overlap between candidate and reference translations",
            "summary": "BLEU = BP * exp(sum w_n log p_n); p_n = modified n-gram precision; BP = brevity penalty; range 0-100; standard metric for translation.",
            "tags": ["bleu", "evaluation", "translation"],
            "body": "## Answer\nBLEU (Papineni et al., 2002):\n\n```\nBLEU = BP * exp(sum_{n=1..4} w_n * log p_n)\n```\n\n- `p_n` = modified n-gram precision: count of n-grams in candidate that appear in any reference, clipped by max count in any reference.\n- `BP` = brevity penalty: `exp(1 - r/c)` if candidate shorter than reference, else 1.\n- Weights default: uniform (0.25 each).\n\nRange 0-100. Higher is better. > 30 is decent; > 50 is good human-translation territory.",
            "source": "https://aclanthology.org/P02-1040/",
        },
        {
            "title": "Perplexity: exponentiated cross-entropy of a probability distribution",
            "summary": "PPL = exp(-1/N * sum log p(x_i)); lower is better; standard evaluation for language models; 20-50 for well-trained small LMs, lower for larger.",
            "tags": ["perplexity", "evaluation", "lm"],
            "body": "## Answer\nPerplexity = exp(cross-entropy) = exp(-1/N * sum log p(x_i))\n\nInterpretation: the effective branching factor the model considers at each step.\n- PPL = 1: model assigns probability 1 to every correct token.\n- PPL = V (vocab size): uniform distribution.\n- PPL = 20-50: well-trained small LM.\n- PPL < 10: strong modern LM.\n\nLarger models generally achieve lower PPL on the same corpus.",
            "source": "https://en.wikipedia.org/wiki/Perplexity",
        },
        {
            "title": "Spearman correlation: rank-based measure of monotonic association",
            "summary": "Pearson correlation on ranks; range -1 to 1; -1 = perfectly anti-monotonic; 0 = no monotonic association; 1 = perfectly monotonic; works for ordinal data and outliers.",
            "tags": ["correlation", "statistics"],
            "body": "## Answer\nSpearman rho = Pearson correlation applied to ranks:\n1. Rank both variables.\n2. Compute Pearson on the ranks.\n\nProperties:\n- Range -1 to 1.\n- Captures monotonic (not just linear) relationships.\n- Robust to outliers (uses ranks, not values).\n- Standard for agreement between ranking systems (e.g., two retrieval methods).",
            "source": "https://en.wikipedia.org/wiki/Spearman%27s_rank_correlation_coefficient",
        },
        {
            "title": "AUC-ROC: area under the receiver operating characteristic curve",
            "summary": "AUC = probability that a random positive ranks above a random negative; 0.5 = random; 1.0 = perfect; threshold-invariant metric for binary classification.",
            "tags": ["auc", "evaluation", "classification"],
            "body": "## Answer\nROC curve: true positive rate vs false positive rate as the classification threshold varies.\n\nAUC = area under that curve.\n\nInterpretation: probability that a randomly chosen positive example is ranked higher than a randomly chosen negative example.\n\n- 0.5 = random\n- 1.0 = perfect separation\n- 0.7-0.8 = decent\n- 0.9+ = strong\n\nThreshold-invariant -- good when the operating threshold isn't fixed.",
            "source": "https://en.wikipedia.org/wiki/Receiver_operating_characteristic",
        },
        {
            "title": "TF-IDF: term frequency times inverse document frequency",
            "summary": "TF(t,d) * IDF(t) = count(t in d) / |d| * log(N / df(t)); rewards words common in a document but rare in the corpus; classic IR baseline before dense retrievers.",
            "tags": ["tfidf", "ir", "lexical"],
            "body": "## Answer\nTF-IDF combines two intuitions:\n- **TF (term frequency)**: words that appear a lot in a document are likely important.\n- **IDF (inverse document frequency)**: words that appear in many documents are less discriminative.\n\nCommon formulation:\n`tfidf(t, d) = tf(t, d) * log(N / df(t))`\n\nWas the standard retrieval baseline for decades. Now dominated by dense retrievers but still competitive for code and exact-match recall.",
            "source": "https://en.wikipedia.org/wiki/Tf%E2%80%93idf",
        },
        {
            "title": "Cosine similarity: angle between two vectors, ignoring magnitude",
            "summary": "cos(theta) = (A . B) / (|A| * |B|); range -1 to 1; standard similarity for normalized embeddings; high = similar direction in vector space.",
            "tags": ["similarity", "embeddings"],
            "body": "## Answer\nCosine similarity = cosine of the angle between two vectors.\n\n`cos(theta) = (A . B) / (|A| * |B|)`\n\nProperties:\n- Range -1 to 1 (1 for normalized vectors, 0 for orthogonal, -1 for opposite).\n- Scale-invariant (only direction matters).\n- The standard similarity for word embeddings, sentence embeddings, and dense retrieval.\n\nWhen vectors are pre-normalized, similarity = dot product -- much faster.",
            "source": "https://en.wikipedia.org/wiki/Cosine_similarity",
        },
        {
            "title": "Sparse vs dense retrieval: when each wins",
            "summary": "Sparse (BM25, TF-IDF): exact term matches, fast, predictable. Dense (embeddings): semantic similarity, robust to vocabulary mismatch. Hybrid fuses both.",
            "tags": ["retrieval", "comparison"],
            "body": "## Answer\nTradeoffs:\n\n**Sparse** (BM25, TF-IDF):\n- Wins on exact term matches (code, error strings, proper nouns).\n- Fast, no model serving.\n- Fails on vocabulary mismatch (\"JWT\" vs \"auth token\").\n\n**Dense** (embeddings):\n- Wins on semantic similarity.\n- Robust to paraphrase.\n- Fails on exact-match recall (rare terms, code symbols).\n\nHybrid (RRF fusion of both) is the production default.",
            "source": "https://en.wikipedia.org/wiki/Sparse_retrieval",
        },
    ],
}


# ---------------------------------------------------------------------------
# Query generation
# ---------------------------------------------------------------------------

CODE_QUERIES = [
    # auth
    ("auth-rotate-001", "how do I rotate the JWT signing key", ["auth-rotate-jwt-key"], True),
    ("auth-rotate-002", "leaked JWT token what do I do", ["auth-leaked-token"], True),
    ("auth-rotate-003", "rotating JWT without breaking active sessions", ["auth-rotate-jwt-key"], False),
    ("auth-design-001", "why ed25519 instead of RSA", ["auth-ed25519-vs-rsa"], True),
    ("auth-design-002", "JWT vs sessions tradeoffs", ["auth-no-sessions"], False),
    ("auth-design-003", "why short-lived tokens", ["auth-no-sessions"], False),
    ("auth-s2s-001", "service to service authentication", ["auth-s2s-tokens"], True),
    ("auth-s2s-002", "how does auth-tokens endpoint work", ["auth-s2s-tokens"], True),
    ("auth-s2s-003", "workload identity for k8s services", ["auth-s2s-tokens"], False),
    ("auth-jwt-001", "user vs service JWT", ["auth-user-vs-service-jwt"], True),
    ("auth-jwt-002", "difference between user and service tokens", ["auth-user-vs-service-jwt"], True),
    ("auth-jwt-003", "audience claim JWT", ["auth-aud-meaning"], True),
    ("auth-jwt-004", "kid header meaning in JWT", ["auth-kid-meaning"], False),
    ("auth-keys-001", "where are JWT public keys stored", ["auth-public-keys"], True),
    ("auth-keys-002", "key rotation secrets manager", ["auth-public-keys"], False),
    ("auth-oauth-001", "OAuth state validation", ["auth-oauth-state"], False),
    # billing
    ("bill-math-001", "how is invoice line total calculated", ["billing-line-math"], True),
    ("bill-math-002", "proration formula", ["billing-line-math", "billing-proration-edge"], True),
    ("bill-math-003", "month boundary proration", ["billing-proration-edge"], True),
    ("bill-fx-001", "currency conversion storage", ["billing-no-fx-storage"], True),
    ("bill-fx-002", "when do we apply the FX rate", ["billing-no-fx-storage"], True),
    ("bill-refund-001", "how are refunds represented", ["billing-refunds"], True),
    ("bill-refund-002", "negative invoice lines", ["billing-refunds"], True),
    ("bill-tax-001", "tax inclusive prices", ["billing-tax-inclusive"], True),
    ("bill-trial-001", "trial period billing", ["billing-trial"], True),
    ("bill-idem-001", "idempotency key invoice creation", ["billing-idempotency"], True),
    ("bill-stripe-001", "stripe webhook signature verification", ["billing-stripe-webhook"], True),
    ("bill-payout-001", "payout reconciliation job", ["billing-payout-recon"], True),
    ("bill-dunning-001", "dunning retry schedule", ["billing-dunning"], True),
    # migrations
    ("mig-safety-001", "add NOT NULL column safely", ["migrations-add-not-null"], True),
    ("mig-safety-002", "rename column without downtime", ["migrations-rename-column"], False),
    ("mig-safety-003", "zero-downtime schema change", ["migrations-zero-downtime", "migrations-rename-column"], True),
    ("mig-online-001", "online vs offline schema change", ["migrations-online-offline"], True),
    ("mig-two-001", "dropping a column when to do it", ["migrations-never-drop-same-release"], True),
    ("mig-timeout-001", "lock timeout in migration", ["migrations-lock-timeout"], True),
    ("mig-test-001", "testing destructive migration", ["migrations-test-destructive"], False),
    ("mig-audit-001", "schema migrations audit table", ["migrations-audit-log"], True),
    ("mig-rollback-001", "how do I roll back a migration", ["migrations-rollback"], True),
    # deploy
    ("deploy-canary-001", "canary window config", ["deploy-canary-window"], True),
    ("deploy-canary-002", "rollout error rate threshold", ["deploy-canary-window"], True),
    ("deploy-rollback-001", "roll back a bad release", ["deploy-rollback-cmd"], True),
    ("deploy-immut-001", "immutable image tags", ["deploy-immutable-tags"], True),
    ("deploy-freeze-001", "deploy freeze calendar", ["deploy-freeze-calendar"], True),
    ("deploy-flag-001", "feature flag rollout order", ["deploy-feature-flags"], True),
    ("deploy-checklist-001", "pre-deploy checklist", ["deploy-pre-checklist"], True),
    ("deploy-pdb-001", "pod disruption budget", ["deploy-pdb"], True),
    ("deploy-vocab-001", "deploy vs release", ["deploy-vs-release"], True),
    ("deploy-debug-001", "stuck rollout debugging", ["deploy-stuck-rollout"], True),
    # observability
    ("obs-slo-001", "billing endpoint SLO", ["obs-slo-billing"], True),
    ("obs-sample-001", "trace sampling strategy", ["obs-trace-sampling"], True),
    ("obs-sample-002", "tail-based sampling", ["obs-trace-sampling"], True),
    ("obs-page-001", "alerting severity levels", ["obs-alert-severity"], True),
    ("obs-page-002", "when do we wake everyone", ["obs-alert-severity"], True),
    ("obs-trace-001", "traceparent header propagation", ["obs-trace-id-prop"], True),
    ("obs-dash-001", "dashboard naming convention", ["obs-dashboard-naming"], True),
    ("obs-log-001", "log levels in production", ["obs-log-levels"], True),
    ("obs-oncall-001", "on-call rotation handoff", ["obs-oncall-rotation"], True),
    ("obs-budget-001", "error budget policy", ["obs-error-budget"], True),
    ("obs-err-001", "what counts as a user-facing error", ["obs-user-facing-err"], False),
    ("obs-req-001", "request ID propagation", ["obs-request-id"], True),
    # testing
    ("test-int-001", "integration test setup", ["testing-integration-org"], True),
    ("test-fix-001", "fixture vs factory", ["testing-fixture-vs-factory"], True),
    ("test-mock-001", "mocking HTTP calls", ["testing-mock-http"], True),
    ("test-cov-001", "coverage gate", ["testing-coverage-gate"], True),
    ("test-flake-001", "flaky test policy", ["testing-flaky"], True),
    ("test-prop-001", "hypothesis property-based testing", ["testing-property-based"], True),
    ("test-snap-001", "snapshot test review", ["testing-snapshots"], True),
    ("test-load-001", "load test execution", ["testing-load"], True),
    ("test-db-001", "transactional DB tests", ["testing-db-transactions"], True),
    ("test-ci-001", "CI parallelization shards", ["testing-ci-parallel"], True),
    # api
    ("api-page-001", "cursor based pagination", ["api-pagination"], True),
    ("api-page-002", "why cursors not offsets", ["api-pagination"], True),
    ("api-rl-001", "rate limiting per API key", ["api-rate-limit"], True),
    ("api-rl-002", "429 too many requests retry", ["api-rate-limit"], True),
    ("api-bulk-001", "bulk endpoint usage", ["api-bulk"], True),
    ("api-ver-001", "API versioning strategy", ["api-versioning"], True),
    ("api-status-001", "401 vs 403 status code", ["api-401-vs-403"], True),
    ("api-err-001", "error response format", ["api-problem-details"], True),
    ("api-expand-001", "expand parameter for related objects", ["api-expand"], True),
    ("api-idem-001", "idempotency key reuse", ["api-idempotency"], True),
    ("api-wh-001", "webhook signature verification", ["api-webhook-sig"], True),
    ("api-shut-001", "graceful shutdown timeout", ["api-graceful-shutdown"], True),
    # data model
    ("dm-uuid-001", "why UUIDv7 instead of UUIDv4", ["dm-uuidv7"], True),
    ("dm-uuid-002", "time-ordered UUID", ["dm-uuidv7"], True),
    ("dm-soft-001", "soft delete column", ["dm-soft-delete"], True),
    ("dm-time-001", "TIMESTAMPTZ vs TIMESTAMP", ["dm-timestamptz"], True),
    ("dm-money-001", "storing monetary amounts", ["dm-money-bigint"], True),
]


PAPER_QUERIES = [
    # Transformer
    ("tx-fmla-001", "transformer attention formula", ["tx-scaled-dot-product"], True),
    ("tx-fmla-002", "scaled dot product attention", ["tx-scaled-dot-product"], True),
    ("tx-fmla-003", "softmax scaling factor in attention", ["tx-scaled-dot-product"], True),
    ("tx-mha-001", "multi-head attention purpose", ["tx-multi-head"], True),
    ("tx-mha-002", "how many heads in transformer base", ["tx-multi-head"], True),
    ("tx-pe-001", "sinusoidal positional encoding", ["tx-positional"], True),
    ("tx-train-001", "training compute transformer base", ["tx-training-compute"], True),
    ("tx-train-002", "how long to train the original transformer", ["tx-training-compute"], True),
    ("tx-bleu-001", "transformer BLEU on WMT", ["tx-bleu-results"], True),
    ("tx-bleu-002", "EN-DE translation improvement transformer", ["tx-bleu-results"], True),
    # BERT
    ("bert-mlm-001", "masked language modeling BERT", ["bert-mlm"], True),
    ("bert-mlm-002", "what fraction of tokens masked", ["bert-mlm"], True),
    ("bert-mlm-003", "why random and unchanged tokens in MLM", ["bert-mlm"], False),
    ("bert-nsp-001", "next sentence prediction BERT", ["bert-nsp"], True),
    ("bert-nsp-002", "is NSP useful", ["bert-nsp"], True),
    ("bert-size-001", "BERT base parameters", ["bert-size"], True),
    ("bert-size-002", "BERT large vs base size", ["bert-size"], True),
    ("bert-data-001", "BERT pretraining corpus", ["bert-pretraining-data"], True),
    # ResNet
    ("rn-skip-001", "residual connection formula", ["resnet-skip"], True),
    ("rn-skip-002", "why skip connections help training", ["resnet-skip"], True),
    ("rn-skip-003", "deep network training problem", ["resnet-skip"], True),
    ("rn-imnet-001", "ResNet ImageNet error rate", ["resnet-imagenet"], True),
    ("rn-imnet-002", "ILSVRC 2015 winner", ["resnet-imagenet"], True),
    ("rn-short-001", "identity vs projection shortcuts", ["resnet-shortcuts"], True),
    ("rn-bottle-001", "bottleneck block ResNet", ["resnet-bottleneck"], True),
    # Adam
    ("adam-def-001", "Adam optimizer formula", ["adam-moments"], True),
    ("adam-def-002", "what are the two moments in Adam", ["adam-moments"], True),
    ("adam-lr-001", "Adam default learning rate", ["adam-default-lr"], True),
    ("adam-lr-002", "Adam vs SGD learning rate", ["adam-default-lr"], True),
    ("adam-eps-001", "epsilon in Adam optimizer", ["adam-epsilon"], True),
    ("adam-w-001", "AdamW weight decay", ["adam-adamw"], True),
    ("adam-w-002", "decoupled weight decay", ["adam-adamw"], True),
    # FlashAttention
    ("fa-tile-001", "FlashAttention tiling approach", ["flashattn-tiling"], True),
    ("fa-tile-002", "why FlashAttention is faster", ["flashattn-tiling"], True),
    ("fa-soft-001", "online softmax FlashAttention", ["flashattn-online-softmax"], True),
    ("fa-soft-002", "block-wise softmax numerical stability", ["flashattn-online-softmax"], False),
    ("fa-hw-001", "FlashAttention hardware requirements", ["flashattn-hardware"], False),
    # LoRA
    ("lora-def-001", "LoRA rank decomposition", ["lora-decomposition"], True),
    ("lora-def-002", "low rank adaptation formula", ["lora-decomposition"], True),
    ("lora-r-001", "LoRA rank size recommendation", ["lora-rank"], True),
    ("lora-r-002", "what rank to use for LoRA", ["lora-rank"], True),
    ("lora-inf-001", "merge LoRA into base model", ["lora-merge"], True),
    ("lora-inf-002", "LoRA inference overhead", ["lora-merge"], True),
    # Dropout
    ("drop-def-001", "dropout regularization", ["dropout-definition"], True),
    ("drop-def-002", "dropout probability hidden vs input", ["dropout-definition"], True),
    ("drop-ens-001", "dropout as ensemble", ["dropout-ensemble"], True),
    # Word2Vec
    ("w2v-skip-001", "skip-gram negative sampling", ["w2v-skipgram"], True),
    ("w2v-skip-002", "Word2Vec training objective", ["w2v-skipgram"], True),
    ("w2v-ana-001", "king man woman queen analogy", ["w2v-analogy"], True),
    ("w2v-d-001", "Word2Vec embedding dimension", ["w2v-dim"], True),
    # DQN
    ("dqn-trick-001", "DQN experience replay", ["dqn-tricks"], True),
    ("dqn-trick-002", "target network DQN", ["dqn-tricks"], True),
    ("dqn-res-001", "DQN Atari results", ["dqn-atari-results"], True),
    ("dqn-res-002", "how many Atari games did DQN beat humans", ["dqn-atari-results"], True),
    ("dqn-clip-001", "DQN reward clipping", ["dqn-reward-clipping"], True),
    # PPO
    ("ppo-def-001", "PPO clipped objective", ["ppo-clipped-objective"], True),
    ("ppo-def-002", "PPO surrogate loss", ["ppo-clipped-objective"], True),
    ("ppo-default-001", "default RL algorithm", ["ppo-default"], True),
    ("ppo-default-002", "PPO vs TRPO", ["ppo-default"], True),
    ("ppo-eps-001", "PPO clipping epsilon", ["ppo-epsilon"], True),
    ("ppo-eps-002", "PPO epsilon value", ["ppo-epsilon"], True),
    # VAE
    ("vae-def-001", "VAE encoder decoder", ["vae-arch"], True),
    ("vae-rep-001", "reparameterization trick", ["vae-reparameterization"], True),
    ("vae-elbo-001", "VAE ELBO", ["vae-elbo"], False),
    # BatchNorm
    ("bn-def-001", "batch normalization", ["bn-formula"], True),
    ("bn-def-002", "batchnorm per mini-batch", ["bn-formula"], True),
    ("bn-lr-001", "batchnorm allows higher learning rate", ["bn-lr-benefit"], True),
    # GELU
    ("gelu-def-001", "GELU activation", ["gelu-definition"], True),
    ("gelu-def-002", "GELU formula transformer", ["gelu-definition"], True),
    ("gelu-stoch-001", "GELU stochastic interpretation", ["gelu-stochastic"], False),
    # YOLO
    ("yolo-def-001", "YOLO real-time detection", ["yolo-realtime"], True),
    ("yolo-grid-001", "YOLO grid cell bounding box", ["yolo-grid"], True),
    # PER
    ("per-def-001", "prioritized experience replay", ["per-td-error"], True),
    ("per-def-002", "PER TD error priority", ["per-td-error"], True),
    # Distillation
    ("dist-def-001", "knowledge distillation", ["dist-soft-labels"], True),
    ("dist-def-002", "distillation soft labels", ["dist-soft-labels"], True),
    ("dist-temp-001", "distillation temperature", ["dist-temperature"], True),
    ("dist-dark-001", "dark knowledge distillation", ["dist-dark-knowledge"], False),
    # GAN
    ("gan-def-001", "GAN generator discriminator", ["gan-arch"], True),
    ("gan-def-002", "generative adversarial network", ["gan-arch"], True),
    ("gan-train-001", "GAN mode collapse", ["gan-mode-collapse"], True),
    ("gan-train-002", "GAN training stability", ["gan-mode-collapse"], False),
    ("gan-wgan-001", "Wasserstein GAN", ["gan-wgan"], True),
    ("gan-wgan-002", "WGAN gradient penalty", ["gan-wgan"], False),
    # LayerNorm / RMSNorm
    ("ln-def-001", "LayerNorm normalization", ["ln-definition"], True),
    ("ln-def-002", "layer norm per example", ["ln-definition"], True),
    ("ln-bn-001", "LayerNorm vs BatchNorm", ["ln-vs-bn"], True),
    ("ln-bn-002", "when to use LayerNorm", ["ln-vs-bn"], True),
    ("rms-def-001", "RMSNorm scaling only", ["rms-definition"], True),
    # MoE
    ("moe-def-001", "sparse mixture of experts", ["moe-routing"], True),
    ("moe-def-002", "MoE top-k routing", ["moe-routing"], True),
    ("moe-lb-001", "MoE load balancing", ["moe-load-balancing"], True),
    ("moe-lb-002", "expert collapse MoE", ["moe-load-balancing"], False),
    # SwiGLU
    ("swiglu-def-001", "SwiGLU activation", ["swiglu-ffn"], True),
    ("swiglu-def-002", "gated linear unit FFN", ["swiglu-ffn"], True),
    # General ML concepts
    ("soft-def-001", "softmax function", ["softmax-definition"], True),
    ("soft-def-002", "softmax formula probability", ["softmax-definition"], True),
    ("ce-def-001", "cross entropy loss", ["ce-definition"], True),
    ("ce-def-002", "cross entropy with softmax", ["ce-definition"], True),
    ("temp-def-001", "sampling temperature", ["temperature-sampling"], True),
    ("temp-def-002", "temperature decoding language model", ["temperature-sampling"], True),
    ("nuc-def-001", "nucleus sampling top-p", ["nucleus-sampling"], True),
    ("nuc-def-002", "top-p sampling", ["nucleus-sampling"], True),
    ("beam-def-001", "beam search decoding", ["beam-search"], True),
    ("gd-def-001", "gradient descent basics", ["gd-basics"], True),
    ("gd-def-002", "SGD mini batch", ["gd-basics"], True),
    ("lr-def-001", "learning rate Adam", ["lr-importance"], True),
    ("lr-def-002", "Adam default learning rate", ["lr-importance"], True),
    ("init-def-001", "Xavier initialization", ["init-xavier-he"], True),
    ("init-def-002", "He Kaiming init", ["init-xavier-he"], True),
    ("tok-def-001", "BPE tokenization", ["tok-bpe"], True),
    ("tok-def-002", "subword tokenization", ["tok-bpe"], True),
    ("spec-def-001", "special tokens", ["tok-special"], True),
    ("bleu-def-001", "BLEU score translation", ["bleu-definition"], True),
    ("bleu-def-002", "BLEU modified n-gram precision", ["bleu-definition"], True),
    ("ppl-def-001", "language model perplexity", ["perplexity-definition"], True),
    ("ppl-def-002", "perplexity evaluation", ["perplexity-definition"], True),
    ("spear-def-001", "Spearman correlation", ["spearman-definition"], True),
    ("spear-def-002", "rank correlation", ["spearman-definition"], True),
    ("auc-def-001", "AUC ROC curve", ["auc-roc"], True),
    ("auc-def-002", "area under ROC", ["auc-roc"], True),
    ("tfidf-def-001", "TF-IDF information retrieval", ["tfidf-definition"], True),
    ("tfidf-def-002", "term frequency inverse document frequency", ["tfidf-definition"], True),
    ("cos-def-001", "cosine similarity embeddings", ["cosine-similarity"], True),
    ("cos-def-002", "cosine similarity formula", ["cosine-similarity"], True),
    ("sd-def-001", "sparse vs dense retrieval", ["sparse-vs-dense"], True),
    ("sd-def-002", "BM25 vs dense retrieval", ["sparse-vs-dense"], True),
]


def main() -> int:
    # ---- code/ pages ----
    from code_slug_map import TITLE_TO_SLUG
    code_pages = 0
    code_uuid_for: dict[str, str] = {}
    for p in CODE_PAGES:
        slug = TITLE_TO_SLUG.get(p["title"])
        if slug is None:
            raise ValueError(
                f"no slug mapping for code page title: {p['title']!r}; "
                f"add it to code_slug_map.py"
            )
        uid = f"code-{slug}"
        write_page(
            CODE_DIR,
            uuid=uid,
            title=p["title"],
            summary=p["summary"],
            tags=p["tags"],
            body=p["body"],
            source=p.get("source", ""),
        )
        code_uuid_for[slug] = uid
        code_pages += 1
    print(f"wrote {code_pages} code/ pages")

    # ---- papers/ pages ----
    from paper_slug_map import TITLE_TO_SLUG as PAPER_TITLE_TO_SLUG
    papers_pages = 0
    paper_uuid_for: dict[str, str] = {}
    for paper, claims in PAPER_CLAIMS.items():
        for c in claims:
            slug = PAPER_TITLE_TO_SLUG.get(c["title"])
            if slug is None:
                # Claim not used by any query; still write it, but use a
                # derived slug.
                head = c["title"].split(":", 1)[-1].strip()
                words = re.findall(r"[A-Za-z][A-Za-z0-9_]+", head)[:5]
                slug = "-".join(w.lower() for w in words)
                print(f"  NOTE: {c['title']!r} not in PAPER_TITLE_TO_SLUG; using derived slug {slug}")
            uid = f"paper-{slug}"
            write_page(
                PAPERS_DIR,
                uuid=uid,
                title=c["title"],
                summary=c["summary"],
                tags=c["tags"],
                body=c["body"],
                source=c.get("source", ""),
            )
            paper_uuid_for[slug] = uid
            papers_pages += 1
    print(f"wrote {papers_pages} papers/ pages")

    # ---- queries ----
    #
    # Each query has a list of `answer_uuids`. Those are the *logical* ids
    # we used while writing the queries (e.g. "auth-rotate-jwt-key"). We
    # resolve them to actual generated UUIDs at build time. Two matching
    # strategies:
    #   1. exact match in the map
    #   2. fallback: treat the id as a slug suffix and scan pages

    def resolve(slug_id: str, uuid_map: dict[str, str]) -> str:
        # 1. exact match
        if slug_id in uuid_map:
            return uuid_map[slug_id]
        # 2. suffix match (slug_id is the suffix of a value)
        candidates = [u for u in uuid_map.values() if u.endswith("-" + slug_id)]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            print(
                f"  WARN: ambiguous slug '{slug_id}' matched "
                f"{len(candidates)} pages; using {candidates[0]}"
            )
            return candidates[0]
        print(f"  WARN: slug '{slug_id}' did not match any page; keeping as-is")
        return slug_id

    code_qs = []
    n_unresolved = 0
    for q in CODE_QUERIES:
        qid, text, ids, stub = q
        resolved = []
        for s in ids:
            r = resolve(s, code_uuid_for)
            resolved.append(r)
            if r == s:
                n_unresolved += 1
        code_qs.append({"qid": qid, "text": text, "answer_uuids": resolved, "stub_sufficient": stub})
    write_queries(QCODE_DIR, code_qs)

    paper_qs = []
    for q in PAPER_QUERIES:
        qid, text, ids, stub = q
        resolved = []
        for s in ids:
            r = resolve(s, paper_uuid_for)
            resolved.append(r)
            if r == s:
                n_unresolved += 1
        paper_qs.append({"qid": qid, "text": text, "answer_uuids": resolved, "stub_sufficient": stub})
    write_queries(QPAPERS_DIR, paper_qs)

    print(f"wrote {len(CODE_QUERIES)} code queries")
    print(f"wrote {len(PAPER_QUERIES)} paper queries")
    if n_unresolved:
        print(f"  ({n_unresolved} unresolved slug ids -- investigate above)")

    return 0


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s[:60] or uuid_mod.uuid4().hex[:8]


if __name__ == "__main__":
    sys.exit(main())
