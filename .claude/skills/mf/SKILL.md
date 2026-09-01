---
name: mf
description: Use the mf memoryfield CLI (`mf search`, `mf read`, `mf write`) to check project memory before exploring a codebase cold, and to write or update memoryfield pages through the dedup gate rather than by hand. Use whenever the working directory (or one given to you) has an `mf.sqlite3` index, or when the user asks you to write, update, or check a memoryfield page.
---

# mf: search-first project memory

`mf` is a local memory index for a project: `search`, `read`, `write`,
and `raw add` are real today (ROADMAP.md 1.1-1.6, 2.1-2.2); `lint` is
not built yet. `raw add` is the session-end staging step (ROADMAP.md
3.1), not a lookup command, so this skill covers the read and write
paths and the page conventions a page still needs to follow so `mf
write`/`mf index`/`mf search` treat it correctly.
The lean-call guidance below (`--limit`/`--neighbor-limit`) comes from a
20-task real-agent trial (ROADMAP.md 1.9), not a guess.

## Do

- **Search before you explore.** Before grepping, walking directories, or
  reading files cold, run `mf search "<question>" --field <dir>`. A field
  with an `mf.sqlite3` already has this indexed; asking first is cheaper
  than rediscovering an answer that's already written down.
- **Keep `mf search` calls lean.** The defaults are now `--limit 3
  --neighbor-limit 1` (ROADMAP.md 2.7). For a direct point lookup,
  `--limit 1 --neighbor-limit 0` is cheaper still: a real-agent trial
  (ROADMAP.md 1.9, `eval/agent_trial_1_9.md`) measured that call at
  ~55 tokens/lookup against ~173 for reading the target page directly,
  and the old defaults (5 / 3) at ~1014, more than the raw read. Widen
  the call only when `confidence` comes back `low`/`none`, or the
  question genuinely needs several related pages at once. The one
  neighbor slot in the default exists to surface a `supersedes` or
  `contradicts` link on the top hit; drop it with `--neighbor-limit 0`
  when you only need the answer.
- **Read the confidence field before trusting the results.**
  `mf search` returns `confidence: high|low|none` alongside the results,
  not just a ranked list:
  - `high` — FTS and dense retrieval agree on the top hit and the
    embedding match is close. Trust the stub. Measured false-high on
    no-answer queries: 1 in 78 (ROADMAP.md 2.7).
  - `low` — one signal passed (a lexical anchor, a close embedding, or
    the two retrievers agreeing on a weak match) but not the pair that
    makes `high`. The stub is right most of the time on a real question,
    and it's also what a question the field can't answer gets 15-30% of
    the time: a topically-adjacent page. Treat it as a lead, not an
    answer. Read the stub critically, escalate to L1 if it's plausible,
    fall back to exploring if it isn't.
  - `none` — nothing passed: no lexical anchor, no close embedding, no
    agreement. What's returned is a best-effort dense guess. Don't cite
    it.
- **Stub-first reading.** `mf search` returns stubs (`uuid`, `title`,
  `summary`, `status`, `tokens`), not full page bodies. Decide relevance
  from the stub and its neighbors before spending a `read` call: the
  summary is written to be the answer, not a teaser, so it's often enough
  on its own (docs/architecture.md's writing conventions).
- **Escalate tiers only when you need to.** `mf read <uuid>` with no
  `--tier` returns L1 (the first section, 150-300 tokens, answer-first).
  Read that before reaching for more. Only call `mf read <uuid> --tier L2`
  when L1 didn't actually answer the question — L2 is rationale, history,
  and edge cases, not required reading for a straightforward lookup. If a
  stub's neighbor or the page's own headings make it clear which specific
  section has the answer, jump straight there with `mf read
  <uuid>#section-slug` instead of pulling all of L2.
- **Read related pages together when it's genuinely useful.** `mf read`
  accepts more than one ref in a single call (`mf read uuid1 uuid2`) and
  records that they were read together (`co_read`, in `links`) — real
  signal for future neighbor ranking (ROADMAP.md 4.4). Only batch refs
  you're actually reading for the same task, not everything a search
  turned up.
- **Write a page with `mf write <path> --field <dir>`, not by hand-editing
  and re-running `mf index`.** `mf write` validates frontmatter and runs
  the dedup gate: it embeds the page and checks it against every other
  page's embedding (the `vec` table's second job, docs/architecture.md).
  If a near-duplicate is found, it refuses (exit code 2) and lists the
  candidates instead of silently creating a second page that says the
  same thing. Genuinely updating an existing page: pass `--update
  <uuid>` (must match the page's own frontmatter `uuid`) to skip the
  gate. Intentionally writing something that looks similar but isn't
  (e.g. a `contradicts` page): pass `--force`. `mf write` indexes the
  page itself on success -- no separate `mf index` call needed
  afterward. `lint` doesn't exist yet, so `mf write` is the only check
  a page gets; still write it following the spec `mf write`/`mf search`
  expect:
  - `summary` is the answer, not the topic: `"Integration tests: make
    test-integration; needs DATABASE_URL"`, not `"Notes on testing."`
  - The first `##` section answers the question; rationale and history
    come after, in later sections.
  - 300-800 tokens per page, 8 KB ceiling. One page per question someone
    would ask, not one page per topic.
  - Verbatim anchors for stable values (commands, hostnames, error
    strings). Pointers, not copied values, for things that drift (SHAs,
    counts, relative dates).
  - Negations go under a `## Don't` heading, or via `status`/`supersedes`
    frontmatter — never only mentioned in prose where a search won't
    surface them as a warning.
  - `key: value` lines instead of tables; no headers under 300 tokens.
  - ISO dates in frontmatter (`created`, `updated`); no relative time
    ("last week") in the body.
  - Fill `source` (URL or path) whenever the memory came from somewhere
    citable.
  - Required frontmatter: `uuid`, `title`. Optional but load-bearing:
    `summary`, `status` (`active`/`superseded`/`contested`), `supersedes`/
    `contradicts`/`depends_on` (lists of uuids), `tags`, `source`, `writer`.
  - Write the file with your normal file-editing tool, then run `mf
    write <path> --field <dir>` to validate, dedup-check, and index it
    in one step. If `mf write` blocks it as a near-duplicate and you
    disagree after checking the listed candidates, that's the judgment
    call `--update`/`--force` exist for (PLAN.md section 10: the gate
    can only inform, the agent decides).

## Don't

- Don't treat `mf search` results as ground truth when `confidence` is
  `none` — verify against the actual code or ask, don't cite it.
- Don't pull L2 by default "just in case." That defeats the token-budget
  point of tiered reading (PLAN.md section 6).
- Don't widen `--limit`/`--neighbor-limit` past the defaults for a
  simple point lookup -- see the lean-call note above. Wide calls are
  for genuinely broad questions, not the common case.
- Don't hand-edit a page file and stop there. Run `mf write` (new page)
  or `mf write --update <uuid>` (existing page) so it's actually
  validated, dedup-checked, and indexed -- a page that's only on disk
  won't show up in `mf search` results, and one written straight into
  the index bypasses the dedup gate entirely.
- Don't reach for `mf lint`, it doesn't exist yet. Don't use `mf raw add`
  during a lookup: it only appends freeform text to `raw/`, which nothing
  indexes or consumes yet (ROADMAP.md 4.2). It's for a session-end
  extract, and the hook that drives it isn't built (ROADMAP.md 3.1).
- Don't `cat`/`Read` a memoryfield page directly when `mf read` would do
  the same job: a direct file read never logs to `reads` or contributes
  to `co_read`, so the field's own retrieval quality never improves from
  it (PLAN.md section 10, accepted gap).

## Command reference (current, not aspirational)

```
mf search "<query>" [--field DIR] [--limit N] [--neighbor-limit N] [--budget N] [--json]
mf read <uuid>[#section] [<uuid2>[#section] ...] [--tier L1|L2] [--field DIR] [--json]
mf write <path> [--field DIR] [--update UUID] [--force] [--json]
mf index [DIR]     # only needed for a page written outside mf write, e.g. a bulk import
```

`--json` on `search`/`read`/`write` gives the machine-readable form if
you're parsing the output yourself rather than reading the rendered
text. `mf write`'s exit code is meaningful: 0 written, 1 invalid input
(bad frontmatter, path outside the field, `--update` uuid mismatch), 2
blocked by the dedup gate (see the `duplicates` list in `--json` output
or the printed candidates).
