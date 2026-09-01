---
name: mf
description: Use the mf memoryfield CLI (`mf search`, `mf read`) to check project memory before exploring a codebase cold, and follow its page conventions when authoring or updating a memoryfield page by hand. Use whenever the working directory (or one given to you) has an `mf.sqlite3` index, or when the user asks you to write, update, or check a memoryfield page.
---

# mf: search-first project memory

`mf` is a local memory index for a project: `search` and `read` are real
today (ROADMAP.md 1.1-1.6); `write`/`raw add`/`lint` are not built yet
(Phase 2/3). This skill covers the read path and the page conventions a
hand-authored page still needs to follow so `mf index` and `mf search`
treat it correctly. It does not cover `write`, which does not exist yet.

## Do

- **Search before you explore.** Before grepping, walking directories, or
  reading files cold, run `mf search "<question>" --field <dir>`. A field
  with an `mf.sqlite3` already has this indexed; asking first is cheaper
  than rediscovering an answer that's already written down.
- **Read the confidence field before trusting the results.**
  `mf search` returns `confidence: high|low|none` alongside the results,
  not just a ranked list:
  - `high` — FTS and dense retrieval agree on the top hit. Trust the stub.
  - `low` — they disagree, or the bm25 floor was barely cleared. The stub
    might still be right; treat it as a lead, not an answer, and be more
    willing to escalate to L2 or fall back to exploring the codebase.
  - `none` — no real FTS hit at all (empty query terms or nothing matched).
    What's returned, if anything, is a best-effort dense guess. Don't
    treat a `none`-confidence result as a citation.
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
- **Follow the page conventions when writing or editing a page by hand.**
  Since `mf write`/`lint` don't exist yet, a hand-authored page only gets
  indexed correctly if it already matches the spec `mf index` and `mf
  search` expect:
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
  - After adding or editing a page, run `mf index [dir]` so it's actually
    searchable — a page on disk that was never indexed won't show up in
    `mf search` results.

## Don't

- Don't treat `mf search` results as ground truth when `confidence` is
  `none` — verify against the actual code or ask, don't cite it.
- Don't pull L2 by default "just in case." That defeats the token-budget
  point of tiered reading (PLAN.md section 6).
- Don't reach for `mf write`, `mf raw add`, or `mf lint` — none of them
  exist yet. Author pages by hand following the conventions above.
- Don't `cat`/`Read` a memoryfield page directly when `mf read` would do
  the same job: a direct file read never logs to `reads` or contributes
  to `co_read`, so the field's own retrieval quality never improves from
  it (PLAN.md section 10, accepted gap).

## Command reference (current, not aspirational)

```
mf search "<query>" [--field DIR] [--limit N] [--neighbor-limit N] [--budget N] [--json]
mf read <uuid>[#section] [<uuid2>[#section] ...] [--tier L1|L2] [--field DIR] [--json]
mf index [DIR]     # re-index after adding/editing a page by hand
```

`--json` on `search`/`read` gives the machine-readable form if you're
parsing the output yourself rather than reading the rendered text table.
