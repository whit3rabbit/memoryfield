# ROADMAP.md 1.9: real-agent trial

N=20 tasks, 2 conditions each (40 runs total), all real Claude
subagents (general-purpose, via the Agent tool) with real tool access
-- not mocked, not scripted answers.

## Methodology

- **Tasks:** 20 straightforward lookup questions against the
  `codebase` domain (75-page corpus), one per page, spanning API/Auth/
  Billing/Deploy/DataModel/Migrations/Observability/Testing. Deliberately
  clearly-phrased (unlike ROADMAP.md 1.8's blind vocabulary-mismatch
  set) -- 1.9 measures operational cost given a normal question, not
  retrieval robustness under mismatch.
- **Condition A (`with_mf`):** agent works in `/tmp/mf-trial/with_mf`
  (75 pages + a real `mf.sqlite3` index, real sqlite-vec + fastembed).
  Told to answer using ONLY the `mf` CLI (`mf search`, `mf read`) --
  no direct file reads.
- **Condition B (`raw`):** same 75 pages, no index, no `mf` mention.
  Agent explores with grep/Read/ls as it normally would in an
  unfamiliar docs directory.
- Every subagent returns a strict structured block (`ANSWER:` +
  `SEARCH_CALLS`/`READ_CALLS` or `FILES_READ:`) so results are
  machine-parseable rather than graded from free narrative.

## Results

**Correctness:** 40/40 answers substantively correct against the known
page content (no hallucinations detected across either condition on
this non-adversarial task set).

**Stub-end rate (condition A):** 20/20 (100%). Every task was answered
from the top `mf search` result's summary alone, zero `mf read` calls.
Matches the corpus's known "stub is the answer" writing discipline
(CLAUDE.md gotcha 8, ~99% stub-sufficiency).

**Wrong-page reads:** condition A: 0/20 (no reads at all, so none
possible). Condition B: 2/20 tasks needed a second file before landing
on the right one (`code-auth-s2s-tokens` also opened
`code-auth-user-vs-service-jwt`; `code-billing-proration-edge` also
opened `code-billing-line-math`) -- both topically adjacent, not
random misses.

**Tokens-to-answer -- the harness-level `subagent_tokens` figure the
Agent tool reports is not a usable signal for this comparison:**
condition A averaged 51,946 tokens/run, condition B averaged 51,926 --
a 0.04% difference, because both conditions pay the same ~50k fixed
per-agent-session overhead (system prompt, tool schemas) regardless of
which retrieval mechanism was used underneath. That overhead swamps
the few-hundred-token difference the retrieval mechanism itself
produces. Measuring the actual mechanism requires isolating the
content tokens each condition put in context -- see
`eval/agent_trial_token_costs.py`, which reproduces this deterministically:

| | avg tokens/task (20 tasks) | vs. raw |
|---|---|---|
| raw (full page read, 1-2 files) | 173.4 | -- |
| `mf search` **default** (`--limit 5 --neighbor-limit 3`) | 1014.4 | **5.85x more** |
| `mf search` **lean** (`--limit 1 --neighbor-limit 0`) | 54.9 | **3.2x less** |

## The central finding

**`mf search`'s default flags cost more tokens than raw file
exploration for a single-answer point lookup.** Every one of these 20
tasks was answerable from the single top stub, but the default
(`--limit 5 --neighbor-limit 3`) renders 5 top-level stubs plus up to
3 neighbor stubs under each -- all of which enter the agent's context
regardless of whether it ends up using any of them. The tool only
delivers the token savings PLAN.md section 6 modeled when called
leanly. See CLAUDE.md gotcha 26 and `.claude/skills/mf/SKILL.md`'s
updated guidance (call `mf search` with a small `--limit` for a direct
point lookup, and widen only if `confidence` comes back `low`/`none`
or the question genuinely needs several related pages).

This doesn't touch `mf/search.py`'s `DEFAULT_LIMIT`/
`DEFAULT_NEIGHBOR_LIMIT` constants themselves -- those were chosen
without this cost data and changing them now would also touch 1.4's
confidence-gate calibration (which was run at `limit=5`), so that's a
separate, deliberate follow-up, not an incidental fix bundled into
this measurement task.

## Raw per-task results

| task | target page | mf search calls | mf read calls | raw files read |
|---|---|---|---|---|
| webhook signature verification | code-api-webhook-sig | 1 | none | code-api-webhook-sig.md |
| pagination | code-api-pagination | 1 | none | code-api-pagination.md |
| service-to-service auth | code-auth-s2s-tokens | 2 | none | code-auth-s2s-tokens.md, code-auth-user-vs-service-jwt.md |
| Ed25519 vs RSA | code-auth-ed25519-vs-rsa | 1 | none | code-auth-ed25519-vs-rsa.md |
| public key storage | code-auth-public-keys | 1 | none | code-auth-public-keys.md |
| Stripe webhook verification | code-billing-stripe-webhook | 1 | none | code-billing-stripe-webhook.md |
| proration boundary edge case | code-billing-proration-edge | 1 | none | code-billing-line-math.md, code-billing-proration-edge.md |
| trial period invoices | code-billing-trial | 1 | none | code-billing-trial.md |
| immutable image tags | code-deploy-immutable-tags | 1 | none | code-deploy-immutable-tags.md |
| stuck rollout debugging | code-deploy-stuck-rollout | 1 | none | code-deploy-stuck-rollout.md |
| pod disruption budget | code-deploy-pdb | 1 | none | code-deploy-pdb.md |
| no foreign keys | code-dm-no-fk | 1 | none | code-dm-no-fk.md |
| TIMESTAMPTZ column type | code-dm-timestamptz | 1 | none | code-dm-timestamptz.md |
| renaming a column | code-migrations-rename-column | 1 | none | code-migrations-rename-column.md |
| online vs offline migrations | code-migrations-online-offline | 1 | none | code-migrations-online-offline.md |
| migration rollback | code-migrations-rollback | 1 | none | code-migrations-rollback.md |
| error budget purpose | code-obs-error-budget | 1 | none | code-obs-error-budget.md |
| on-call rotation | code-obs-oncall-rotation | 1 | none | code-obs-oncall-rotation.md |
| PR coverage gate | code-testing-coverage-gate | 1 | none | code-testing-coverage-gate.md |
| integration test organization | code-testing-integration-org | 1 | none | code-testing-integration-org.md |

## What this replaces

PLAN.md section 6's savings table was modeled, not measured (its own
header says so). This is the first real-agent measurement against
that model. The two numbers don't map cleanly onto the modeled
table's cells (this trial didn't include a "wrong-page reads at scale"
scenario or a multi-hop task), but the qualitative story is closer to
the model than 1.4-1.8's other calibration surprises: the tool is
capable of large token savings on real single-answer lookups, but only
when called with the right shape of request -- and the default shape
of request is not that shape. That's new information the model didn't
have.
