# mf: architecture reference

Standalone reference for the schema and retrieval design. Full rationale
and the "why" behind each stack choice lives in [PLAN.md](../PLAN.md).
The evidence behind each retrieval decision lives in
[M0.5_REPORT.md](../M0.5_REPORT.md). This doc states what the design
currently is, not why it got there.

## Layers

Five layers. The first is the spec, the rest are derived or conventional.

### 1. Pages (canonical)

Memoryfield-spec Markdown with frontmatter. Extended fields, all
optional so plain memoryfields still load:

```
uuid, title, created, updated          # spec
summary:      one line, written as the answer, not the topic
status:       active | superseded | contested
supersedes:   [uuid]
contradicts:  [uuid]
depends_on:   [uuid]
tags:         [..]
source:       url or path                # citation slot
writer:       agent-or-person id
```

Body convention: first section is L1 (answer-first, 150-300 tokens),
later sections are L2. Sections are addressable as `uuid#slug`.

### 2. Index (derived, deletable)

One SQLite file, `mf.sqlite3`, inside the field:

```
pages   (uuid PK, filename, title, summary, status, tokens, sha256, updated, writer)
sections(uuid, slug, ordinal, byte_start, byte_end, tokens)
fts     -- FTS5 over title, summary, body (full page)
vec     -- sqlite-vec, embedding of title+summary+L1 only, model-tagged
links   (src, dst, kind, weight)      -- kind: supersedes|contradicts|depends_on|co_read
claims  (slug, claimed_by, claimed_at) -- for multi-writer create/update resolution
```

Dense covers L0+L1 (what a page is *for*), FTS covers the full body
(the port number in paragraph six). Neither is precomputed against the
other: kNN neighbors are computed at query time from `vec`, so they
never go stale. Only typed links and co-reads are stored.

The `vec` table backs three separate features, not one (CLAUDE.md
gotcha 14): kNN neighbor stubs, write-time dedup of near-duplicate
pages, and fallback ranking when FTS returns nothing. Losing the
ranking argument for dense (see below) doesn't touch the other two.

### 3. Retrieval

`search` runs **FTS5 first, dense as a gated fallback**, not fused.
This is the M0.5 gate decision (CLAUDE.md gotcha 13), reversing the
plan's original symmetric-RRF hybrid:

1. FTS answers first. No model server, no embedder warmup, no version
   drift, instant incremental indexing.
2. Dense runs as the recall net when FTS's score gate signals low
   confidence, not fused in unconditionally. Symmetric RRF at equal
   weights has nothing to add once both signals are near ceiling.
3. Results return as the top-k stubs (uuid, title, summary, status,
   tokens) with up to n neighbor stubs each (typed links first, then
   kNN, then co_read). Superseded pages return only as a
   `superseded_by` pointer on the winner.
4. Reranker (cross-encoder over the top 20) is cut, not deferred,
   unless the blind vocabulary-mismatch query set (roadmap 1.8) shows
   P@3 dropping below ~0.8. See M4 in the roadmap.

Output is JSON or a compact text table. The agent never sees a body
unless it asks.

**Confidence gate, not yet built, the actual M1 blocker** (CLAUDE.md
gotcha 15). `search` currently has no notion of "no answer here."
Needed before M1 ships: a per-query floor plus relative-gap heuristic,
calibrated on the 30 no-answer queries, exposed as `confidence:
high|low|none` on every result set.

### 4. Read

`read uuid[#section] --tier L1|L2` returns exactly that slice, logs
the read, and increments `co_read` for pages read in the same call.
`co_read` only sees reads that go through this path: an agent that
`cat`s a page bypasses it (accepted risk, PLAN.md section 10).

### 5. Write (M2, not yet built)

`write` validates frontmatter and runs the dedup gate: dense
similarity against existing stubs (the `vec` table's second job),
returning near-duplicates with a nonzero exit code. `--update uuid` /
`--force` are the escape hatches. Dedup is an LLM judgment the tool
can only inform: the gate returns candidates, the agent decides
(PLAN.md section 10).

`lint` enforces the writing conventions below and is load-bearing, not
cosmetic (CLAUDE.md gotcha 16): every retrieval quality number this
project has measured holds because page summaries are information-dense,
and that density is a writing-discipline property, not a retrieval
one. If `lint` isn't enforced, retrieval quality drifts, and the M1
design verdict above changes with it.

## Writing conventions (enforced by `lint`, taught by the skill)

- `summary` is the answer: "Integration tests: `make test-integration`;
  needs `DATABASE_URL`", not "Notes on testing."
- First section answers, and rationale and history follow.
- 300-800 tokens per page, 8 KB ceiling.
- One page per question someone would ask, not per topic.
- Verbatim anchors for stable values (commands, hostnames, error
  strings). Pointers for moving values (SHAs, counts).
- Negations under `## Don't` and via `status`/`supersedes`, never only
  in prose.
- `key: value` lines instead of tables. No headers under 300 tokens.
  Code fences only around real commands.
- ISO dates in frontmatter, no relative time in bodies.
- `source` filled whenever the memory came from somewhere.

## Stack

- Python for v1, distributed via `uv tool install`. `sqlite-vec` and
  FTS5 in-process, embeddings via `fastembed` (ONNX runtime), no model
  server. Rust port only if install friction becomes the top
  complaint, and only after the schema stops changing (it changed
  through M0-M2).
- Embedder: `nomic-embed-text-v1.5` (270 MB, 768-d, asymmetric
  `search_query:`/`search_document:` prefixes). M0.5 confirmed
  `bge-large-en-v1.5` is within noise of nomic on this corpus and
  costs ~1 GB more, so nomic stays the default (CLAUDE.md gotcha 3 on
  the prefix trap, gotcha 4 on running nomic and bge in separate
  processes).
- Reranker: none by default, see the M4 condition above.
- LLM: none. Extraction and consolidation are done by the host agent
  that's already running, the tool never calls an LLM itself.

## Where the open decisions are tracked

- Milestone list and scope per milestone: [PLAN.md](../PLAN.md) section 9.
- Numbered gotchas referenced above by number: [CLAUDE.md](../CLAUDE.md).
- Eval evidence behind the retrieval design: [M0.5_REPORT.md](../M0.5_REPORT.md).
