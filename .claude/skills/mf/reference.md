# mf skill reference

The measurements and conventions behind [SKILL.md](SKILL.md). SKILL.md
is what loads when the skill triggers; this file is read on demand.

## Why the lean call

A 20-task real-agent trial (ROADMAP.md 1.9, `eval/agent_trial_1_9.md`)
measured content tokens per lookup:

| Call | Tokens per lookup |
|---|---|
| raw file exploration, no index | ~173 |
| `mf search` at the original defaults (`--limit 5 --neighbor-limit 3`) | ~1009 |
| `--limit 3 --neighbor-limit 1` | ~304 |
| **`--limit 2 --neighbor-limit 0` (the default since 2.11)** | **~104** |
| `--limit 1 --neighbor-limit 0` | ~55 |

Each stub is ~50 tokens and each neighbor slot roughly doubles the
call. Every trial task was answered from the top stub alone, and the
answer was on screen at every setting, so neighbors bought nothing
there. Two stubs keep one fallback for a wrong top-1. `--neighbor-limit
1` shows the top hit's linked pages (`depends_on`, `contradicts`, then
nearest by embedding); `supersedes` is already resolved inline.

## What `confidence` means

Three signals (ROADMAP.md 2.7, `mf/confidence.py`): a lexical floor on
the FTS top score, a cosine floor on the embedding top hit, and whether
the two retrievers agree on the top page.

- `high`: agreement and a close embedding. Measured false-high on 78
  no-answer queries: 1.
- `low`: one signal passed. On a real question the stub is right most
  of the time. On a question the field can't answer, this is what you
  get 15-30% of the time: a topically-adjacent page. Read critically.
- `none`: nothing passed. What's returned is a best-effort guess.

Usable answers on blind (vocabulary-mismatched) questions: 0.90
(codebase) / 0.85 (papers). Ranking is dense-first; FTS is a gate
signal only.

## Read tiers

`mf read <uuid>` with no `--tier` returns L1: the first section,
answer-first, 150-300 tokens. `--tier L2` is everything after it
(rationale, history, edge cases), possibly empty. `<uuid>#slug` returns
one named section regardless of tier. Reads are logged; a multi-ref
call bumps `co_read` between every pair (future neighbor-ranking
signal, ROADMAP.md 4.4).

## Writing a page

Why the draft goes outside the field: the dedup gate can only refuse
to index. A draft already inside the field is a valid page file, and
the next `mf index` indexes it whether or not the gate blocked it.
`mf write` copies a passing draft to `field/<draft name>` (or
`--dest NAME`) and indexes only that page. `mf write - --dest NAME`
reads the draft from stdin.

The gate embeds the page (title + summary + first section) and blocks
if any existing page is within cosine distance 0.10 (ROADMAP.md 2.5,
2.10). It catches copies and light rewordings; a thorough rewrite of
an existing page gets past it about one time in eight, so search
before writing. `--update <uuid>` (must match the page's own `uuid`, edit the
existing file in place) and `--force` skip it. `mf write` checks
frontmatter and duplicates; `mf lint` checks the conventions below and
reports index drift (stale, unindexed, or missing pages). Errors and
warnings fail `--check`; `--all` also prints the advice-level findings
(missing `source`, no typed links, a negation outside `## Don't`).

- `summary` is the answer, not the topic: `"Integration tests: make
  test-integration; needs DATABASE_URL"`, not `"Notes on testing."`
- The first `##` section answers the question. Rationale and history
  come after, in later sections.
- Up to 800 tokens per page, 8 KB ceiling (the eval corpus averages
  ~240). One page per question someone would ask, not one page per
  topic. One headed section until 300 tokens, `## Don't` excepted.
- Verbatim anchors for stable values (commands, hostnames, error
  strings). Pointers, not copied values, for things that drift (SHAs,
  counts, relative dates).
- Negations go under a `## Don't` heading, or via `status`/`supersedes`
  frontmatter, never only in prose.
- `key: value` lines instead of tables. No headers under 300 tokens.
- ISO dates in frontmatter (`created`, `updated`). No relative time in
  the body.
- Fill `source` (URL or path) whenever the memory came from somewhere
  citable.
- Required frontmatter: `uuid`, `title`. Optional but load-bearing:
  `summary`, `status` (`active`/`superseded`/`contested`),
  `supersedes`/`contradicts`/`depends_on` (lists of uuids), `tags`,
  `source`, `writer`. A title or summary containing `: ` is fine (the
  parser quotes values), but avoid a leading `[` or `{`.

To retire a page, write the replacement with `supersedes: [old-uuid]`.
`mf search` then shows the replacement, annotated
`supersedes: old-uuid`, wherever the old page would have matched, and
never shows the old page as a neighbor of its replacement.

## Exit codes and JSON

`--json` on `search`/`read`/`write` gives the machine-readable form.

- `mf write`: 0 written (`path` in the output is field-relative), 1
  invalid input (bad frontmatter, `--update` uuid mismatch, destination
  clash: an existing file with another uuid, or a uuid already indexed
  under another filename), 2 blocked by the dedup gate (`duplicates`
  lists uuid, title, summary, distance; a `warning` is set when the
  draft was inside the field).
- `mf search`: 0 ok, 1 no field, 3 the index is stale for a page it
  would have shown (a file changed or vanished since `mf index`). Run
  `mf index`, or re-run with `--stale-ok` to get the results with those
  stubs marked `stale`.
- `mf read`: 0 ok, 1 unknown uuid or section.

## Other commands

`mf index [DIR]` is the un-gated bulk path: imports, hand edits, or
after a stale refusal. `mf raw add [text]` appends a freeform session
extract to `raw/`, which nothing indexes; it is the session-end staging
step (ROADMAP.md 3.1), not something to call during a lookup. `mf init
[DIR] [--model nomic-embed-text-v1.5|bge-large-en-v1.5]` creates the
index; the model is fixed per field. `mf pack [DIR]` writes
`<name>.memoryfield.zip` plus a `.sha256` sidecar (index included);
`mf unpack ZIP [DEST]` verifies the digest and extracts, and the
extracted index works as-is.
