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
config  (key, value)                  -- model_code, embedding_dim, schema_version
reads   (id, uuid, section, tier, read_at) -- append-only log written by `mf read`
```

Dense covers L0+L1 (what a page is *for*), FTS covers the full body
(the port number in paragraph six). Neither is precomputed against the
other: kNN neighbors are computed at query time from `vec`, so they
never go stale. Only typed links and co-reads are stored.

`config`'s three keys are what make "never conflate model versions"
enforceable rather than aspirational: `model_code` defaults to
`nomic-embed-text-v1.5`, `embedding_dim` to `768` (the `vec` table's
fixed vector width), `schema_version` to `1`. Set once by `mf init`,
read by `mf index`/`mf search` on every call.

The `vec` table backs three separate features, not one (CLAUDE.md
gotcha 14): kNN neighbor stubs, write-time dedup of near-duplicate
pages, and fallback ranking when FTS returns nothing. Losing the
ranking argument for dense (see below) doesn't touch the other two.

### 3. Retrieval

`search` (`mf/search.py`, ROADMAP.md 1.5) runs **FTS5 first; dense
never fuses into or re-ranks FTS's results.** This is the M0.5 gate
decision (CLAUDE.md gotcha 13), reversing the plan's original
symmetric-RRF hybrid:

1. FTS answers first. No model server, no embedder warmup, no version
   drift, instant incremental indexing.
2. Dense still runs on every query, not fused into ranking but not a
   true fallback either: the confidence gate's high/low signal is
   FTS/dense top-1 agreement (see below), and that needs both every
   time. Dense's own top-k becomes the *result set* only in the one
   case FTS has nothing at all (empty MATCH expression or zero hits) --
   that's the `vec` table's fallback-ranking job.
3. Results return as the top-k stubs (uuid, title, summary, status,
   tokens; `k=5` by default, `mf search --limit`) with up to n
   neighbor stubs each (`n=3` by default, `--neighbor-limit`; typed
   links first, then kNN; co_read is a documented no-op until `mf
   read`/1.6 populates it). Superseded pages return only as a
   `{uuid, superseded_by}` pointer, not a full stub.
4. Reranker (cross-encoder over the top 20) is cut, not deferred,
   unless the blind vocabulary-mismatch query set (roadmap 1.8) shows
   P@3 dropping below ~0.8. See M4 in the roadmap.

Output is JSON or a compact text table. The agent never sees a body
unless it asks.

**Confidence gate: calibrated and wired into `search`** (CLAUDE.md
gotcha 15/18/19). `mf/confidence.py` computes `confidence: high|low|none`
from two signals, not one heuristic: FTS's bm25 score normalized by
matched-term count decides none vs. not-none (raw magnitude alone
doesn't separate no-answer from real-answer queries on this corpus,
and is corpus-size-dependent besides); FTS/dense top-1 agreement
decides high vs. low.

Calibrated numbers (`eval/calibrate_confidence.py`, methodology and
full trade-off table there):

| Constant / measurement | Value |
|---|---|
| `FLOOR` (normalized bm25, `mf.confidence.FLOOR`) | `2.0` |
| FTS/dense top-1 agreement, genuinely correct hits | 97.0% |
| FTS/dense top-1 agreement, no-answer queries | 16.7% |
| False-high-confidence rate at `FLOOR=2.0` (30-query no-answer set) | 0% |
| Correct hits demoted to `none` at `FLOOR=2.0` | 19.8% |

The 19.8% figure is an accepted, deliberate cost, not a bug: it's the
price of a true 0% false-high rate on this corpus. All of these numbers
are conditional on the corpus/query-set relationship in gotcha 7 (the
query set was authored from the corpus) and are the ones roadmap 1.8's
blind query set is meant to re-test.

### 4. Read

**Built (ROADMAP.md 1.6).** `mf/read.py`, wired into `mf/cli.py`:
`read uuid[#section] --tier L1|L2` (one or more refs per call) returns
exactly that slice, logs the read to the `reads` table, and for a
multi-ref call increments `co_read` weight in `links` for every pair
of uuids in that call (canonical `src < dst` ordering, so weight
accumulates on one row across calls rather than splitting across both
directions). `co_read` only sees reads that go through this path: an
agent that `cat`s a page bypasses it (accepted risk, PLAN.md section
10). Content is never cached in the index -- each call re-parses the
page fresh off disk via `mf.page.load_page()`, keyed by the `filename`
column in `pages`. A bare uuid with no `--tier` defaults to L1
(answer-first, matching the intended stub -> L1 -> L2 escalation
order). L2 is everything after the first section, concatenated,
possibly empty on a single-section page. Verified end to end against
the real 157-page corpus: L1/L2 tiers, named-section refs, the
not-found error path, and co_read weight accumulation across repeated
calls.

### 5. Write

**Built (ROADMAP.md 2.1).** `mf/write.py`, wired into `mf/cli.py`:
`write <path> [--field DIR] [--update UUID] [--force] [--json]`. The
page must already exist as a Markdown file inside the field directory
(same convention as `read`/`index` -- `write` doesn't create the file,
it validates and commits one that's already there). It parses via
`mf.page.load_page()` (raises on missing `uuid`/`title`, same as
`index`), then runs the dedup gate: embeds the page (`document_text()`,
the same function `index` uses) and kNN-queries `vec` for existing
pages within `DEDUP_THRESHOLD` L2 distance, excluding the page's own
uuid (so re-writing an existing page in place never dedup-blocks
against itself). A hit returns the candidates and exit code 2 without
writing anything. `--update UUID` (must match the page's own
frontmatter `uuid`) or `--force` skip the gate. On a pass, `write`
calls the same `indexer.index_field()` `mf index` uses, so a
successful `write` needs no separate `index` call.

`DEDUP_THRESHOLD` (7.0) is a first-cut estimate, not calibrated like
`mf/confidence.py`'s `FLOOR` (CLAUDE.md gotcha 18): one synthetic
probe put a paraphrased near-duplicate of a real corpus page at L2
distance ~4.9 from the original, against ~10.2 for the nearest
genuinely-different-but-related page -- a wide gap on that one
example, not a calibrated boundary. Verified against the real corpus
(not just the synthetic probe): a hand-written paraphrase of an actual
page landed at distance 5.74, correctly blocked.

Dedup is deliberately a gate, not just an FYI (PLAN.md section 10:
"an LLM judgment the tool can only inform," but the tool still has to
have an opinion to gate on) -- `--force`/`--update` are how the
calling agent overrides that opinion once it's made the actual
judgment call.

**`raw add` built (ROADMAP.md 2.2).** `mf/raw.py`, wired into
`mf/cli.py`: `raw add [text] [--field DIR] [--json]` (reads stdin if
`text` is omitted). Appends a freeform session extract as a
timestamped file under `raw/`, the staging area PLAN.md's spec
requires implementations not index (`mf/indexer.py`'s `_SKIP_DIRS` now
includes `raw`, closing a real gap: before 2.2 nothing skipped it
explicitly, and a raw extract that happened to parse as valid
frontmatter could have been silently indexed as a page). Guards
against a session-end hook double-firing: if the new text is a prefix
of the most recent `raw/` entry, or vice versa, the call is a no-op
(no new file, no error) rather than writing a near-identical
duplicate. `consolidate --plan` (ROADMAP.md 4.2, not yet built) is
what eventually turns a `raw/` entry into a real page via `write`.

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
  processes). `mf/indexer.py`'s `MODEL_REGISTRY` currently only wires
  up nomic -- bge is evaluated in the eval harness but isn't yet a
  selectable `mf init` option.
- Reranker: none by default, see the M4 condition above.
- LLM: none. Extraction and consolidation are done by the host agent
  that's already running, the tool never calls an LLM itself.

## Where the open decisions are tracked

- Milestone list and scope per milestone: [PLAN.md](../PLAN.md) section 9.
- Numbered gotchas referenced above by number: [CLAUDE.md](../CLAUDE.md).
- Eval evidence behind the retrieval design: [M0.5_REPORT.md](../M0.5_REPORT.md).
- Confidence gate calibration methodology and full trade-off table:
  `eval/calibrate_confidence.py`.
