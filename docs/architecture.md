# mf: architecture reference

Standalone reference for the schema and retrieval design. Full rationale
and the "why" behind each stack choice lives in [PLAN.md](../PLAN.md).
The evidence behind each retrieval decision lives in
[M0.5_REPORT.md](../M0.5_REPORT.md). This doc states what the design
currently is, not why it got there. Where the built thing and the
intended thing differ, both are stated and the roadmap item that closes
the gap is named.

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

### 2. Index (derived, mostly deletable)

One SQLite file, `mf.sqlite3`, inside the field:

```
pages   (uuid PK, filename, title, summary, status, tokens, sha256, updated, writer)
sections(uuid, slug, ordinal, byte_start, byte_end, tokens)
fts     -- FTS5 over title, summary, body (full page)
vec     -- sqlite-vec, embedding of title+summary+L1 only
links   (src, dst, kind, weight)      -- kind: supersedes|contradicts|depends_on|co_read
claims  (slug, claimed_by, claimed_at) -- for multi-writer create/update resolution
config  (key, value)                  -- model_code, embedding_dim, schema_version
reads   (id, uuid, section, tier, read_at) -- append-only log written by `mf read`
```

**What is and isn't rebuildable.** `pages`, `sections`, `fts`, `vec`,
and the three typed link kinds are derived from the files and come back
identical from `mf index`. Three things are not: the `reads` log,
`co_read` rows in `links`, and `claims`. They accumulate from tool calls
and have no other source, so deleting `mf.sqlite3` loses them. `mf
index` preserves `co_read` across page edits and drops it only when the
page's file is gone (fixed during the Phase 2 review, it used to wipe
it on every upsert). `reads` has no call-group column, so `co_read`
can't be rebuilt from it either. ROADMAP.md 2.5 adds `reads.call_id`
so that at least becomes possible.

`pages.filename` is stored relative to the field directory (POSIX
form), so the index survives the field moving: a fresh clone, or the
`pack`/`unpack` round trip 2.4 needs. `mf read` joins it back onto the
`--field` it was given. An index built before this holds absolute paths
and keeps working until the next `mf index` rewrites them.

Dense covers L0+L1 (what a page is *for*), FTS covers the full body
(the port number in paragraph six). Neither is precomputed against the
other: kNN neighbors are computed at query time from `vec`, so they
never go stale. Only typed links and co-reads are stored.

`config`'s three keys are what make "never conflate model versions"
enforceable rather than aspirational: `model_code` defaults to
`nomic-embed-text-v1.5`, `embedding_dim` to `768` (the `vec` table's
fixed vector width), `schema_version` to `1`. Set once by `mf init`,
read by `mf index`/`mf search` on every call. Model identity lives here,
at the index level, not per `vec` row.

**Distance metric, as built.** `vec` is a `vec0` table with the default
metric, Euclidean L2, over raw fastembed output. The nomic vectors are
not unit-normalized (norm around 20, measured), so every distance the
tool computes, kNN neighbor order, the FTS/dense agreement signal, and
`mf write`'s dedup threshold, is raw L2 on variable-norm vectors. The
eval baselines and the 1.4 gate calibration normalized and used cosine.
That is a calibration/production mismatch of the same shape as CLAUDE.md
gotcha 18 (see gotcha 32), and ROADMAP.md 2.5 moves `vec` to cosine
before anything is recalibrated on top of it.

The `vec` table backs three separate features, not one (CLAUDE.md
gotcha 14): kNN neighbor stubs, write-time dedup of near-duplicate
pages, and fallback ranking when FTS returns nothing.

### 3. Retrieval

`search` (`mf/search.py`, ROADMAP.md 1.5) runs **FTS5 first. Dense runs
on every query but is never fused into or re-ranked against FTS's
list.** This was the M0.5 gate decision (CLAUDE.md gotcha 13), reversing
the plan's original symmetric-RRF hybrid, and it is now scheduled for a
re-decision (ROADMAP.md 2.6). The reasoning, then and now:

1. FTS answers first. The original argument was "no model server, no
   embedder warmup." That argument no longer holds: dense runs on every
   query anyway (point 2), so the cost is paid whether or not dense
   ranks.
2. Dense runs on every query because the confidence gate's high/low
   signal is FTS/dense top-1 agreement (below), and that needs both.
   Dense's own top-k becomes the *result set* only in the one case FTS
   has nothing at all (empty MATCH expression or zero hits). On the
   blind query set that branch fired 0% of the time (ROADMAP.md 1.8),
   because OR-joined tokenization nearly always finds some overlap.
3. The decision was made where it couldn't matter. Both signals were at
   ceiling on the in-vocabulary set. The first data where they diverge
   is the blind set, and there dense wins on the codebase domain:

   | codebase, blind (n=24) | P@3 | MRR |
   |---|---|---|
   | fts | 0.85 | 0.79 |
   | dense_nomic | 1.00 | 0.975 |
   | hybrid (RRF) | 1.00 | 0.925 |

   ROADMAP.md 1.8 reported the two-domain average (0.925 for FTS), which
   hid this. Papers held for both. 2.6 re-runs the choice through the
   real `mf search` pipeline, FTS-first vs RRF vs dense-first.
4. Results return as the top-k stubs (uuid, title, summary, status,
   tokens; `k=5` by default, `mf search --limit`) with up to n neighbor
   stubs each (`n=3` by default, `--neighbor-limit`, typed links first,
   then kNN). `co_read` rows exist and accumulate from `mf read` but are
   not consulted for neighbor ranking yet (ROADMAP.md 4.4).
5. Superseded pages, as built, return as a `{uuid, superseded_by}`
   pointer that **occupies a result slot**. PLAN.md section 2 put the
   pointer on the winner instead. The difference matters under the lean
   call the skill teaches (`--limit 1`): a superseded top hit yields one
   pointer and no answer. ROADMAP.md 2.8 resolves the superseder inline.
6. Reranker (cross-encoder over the top 20) was to be cut unless the
   blind set showed P@3 under ~0.8. 1.8 ran that test and baseline P@3
   held, but the metric was wrong: what matters is the tool's own top-1
   through the gate, which on the blind set is 0.70 (codebase) and 0.80
   (papers). ROADMAP.md 4.1 re-decides against that metric after 2.6/2.7.

Output is JSON or a compact text table. The agent never sees a body
unless it asks.

**Confidence gate: calibrated, wired into `search`, and known to be
miscalibrated for realistic phrasing.** `mf/confidence.py` computes
`confidence: high|low|none` from two signals: FTS's bm25 score
normalized by matched-term count decides none vs. not-none, and
FTS/dense top-1 agreement decides high vs. low.

Calibrated numbers (`eval/calibrate_confidence.py`) next to the blind
re-test (ROADMAP.md 1.8, `eval/blind_fallback_check.py`):

| Measurement | In-vocabulary set | Blind set |
|---|---|---|
| `FLOOR` (normalized bm25, `mf.confidence.FLOOR`) | 2.0 | same |
| FTS/dense top-1 agreement, correct hits | 97.0% | not re-measured |
| FTS/dense top-1 agreement, no-answer queries | 16.7% | not re-measured |
| False-high-confidence on no-answer queries | 0% (n=30) | 1/8 |
| Correct hits demoted to `none` | 19.8% | 45% (both domains) |
| Tool top-1 accuracy, real-answer queries | 0.83 / 0.88 | 0.70 / 0.80 |

Three caveats, in order of weight:

- The "accepted cost" of 19.8% is 45% on blind phrasing, and the skill
  tells the agent not to cite a `none` result. Read jointly with 1.9
  (whose tasks were deliberately in-vocabulary), roughly half of
  realistic lookups pay for the search and then fall back to raw
  exploration. That undercuts PLAN.md section 6's savings case, which
  neither 1.8 nor 1.9 noticed on its own.
- The floor is corpus-size dependent (bm25's IDF term). A 4-page field
  reads permanently `none` at `FLOOR=2.0` (ROADMAP.md 1.5). Real fields
  start small.
- The agreement signal was calibrated on cosine top-1 and runs in
  production on raw L2 top-1 (section 2).

ROADMAP.md 2.7 recalibrates on the blind sets with a larger blind
no-answer sample and a corpus-size sweep, after 2.5 fixes the metric.

### 4. Read

**Built (ROADMAP.md 1.6).** `mf/read.py`, wired into `mf/cli.py`:
`read uuid[#section] --tier L1|L2` (one or more refs per call) returns
exactly that slice, logs the read to the `reads` table, and for a
multi-ref call increments `co_read` weight in `links` for every pair
of uuids in that call (canonical `src < dst` ordering, so weight
accumulates on one row across calls rather than splitting across both
directions). `co_read` only sees reads that go through this path: an
agent that `cat`s a page bypasses it (accepted risk, PLAN.md section
10). Content is never cached in the index. Each call re-parses the
page fresh off disk via `mf.page.load_page()`, resolving the
field-relative `filename` column against the `--field` directory. A
bare uuid with no `--tier` defaults to L1 (answer-first, matching the
intended stub -> L1 -> L2 escalation order). L2 is everything after the
first section, concatenated, possibly empty on a single-section page.
Verified end to end against the real 157-page corpus, including after
moving the field directory.

### 5. Write

**Built (ROADMAP.md 2.1).** `mf/write.py`, wired into `mf/cli.py`:
`write <path> [--field DIR] [--update UUID] [--force] [--json]`. The
page must already exist as a Markdown file inside the field directory.
It parses via `mf.page.load_page()` (raises on missing `uuid`/`title`,
same as `index`), then runs the dedup gate: embeds the page
(`document_text()`, the same function `index` uses) and kNN-queries
`vec` for existing pages within `DEDUP_THRESHOLD` (7.0, raw L2, see
section 2), excluding the page's own uuid. A hit returns the candidates
and exit code 2 without writing anything. `--update UUID` (must match
the page's own frontmatter `uuid`) or `--force` skip the gate. On a
pass, `write` calls the same `indexer.index_field()` `mf index` uses.

**Known limitation: the gate gates the index, not the file.** A blocked
page is still on disk. The next `mf index`, or a `mf write` of any
*other* page (which reindexes the whole field), indexes it with no
dedup check at all. The gate is therefore advisory in practice, which
is not what PLAN.md section 2 describes. ROADMAP.md 2.8 changes `write`
to take a draft from outside the field, copy it in only on a pass, and
index only that page.

`DEDUP_THRESHOLD` is a first-cut estimate, not calibrated like
`mf/confidence.py`'s `FLOOR` (CLAUDE.md gotcha 27): one synthetic probe
put a paraphrased near-duplicate at L2 distance ~4.9 from the original,
against ~10.2 for the nearest genuinely-different-but-related page.
Confirmed against the real corpus (a hand-written paraphrase of an
actual page landed at 5.74, correctly blocked). Because the vectors are
unnormalized, those distances are in units that vary with vector norm.
ROADMAP.md 2.10 builds a labeled near-duplicate set and re-expresses the
threshold in cosine after 2.5.

Dedup is deliberately a gate, not just an FYI (PLAN.md section 10):
`--force`/`--update` are how the calling agent overrides the tool's
opinion once it's made the actual judgment call.

**`raw add` built (ROADMAP.md 2.2).** `mf/raw.py`, wired into
`mf/cli.py`: `raw add [text] [--field DIR] [--json]` (reads stdin if
`text` is omitted). Appends a freeform session extract as a
timestamped file under `raw/`, the staging area PLAN.md's spec
requires implementations not index (`mf/indexer.py`'s `_SKIP_DIRS`
includes `raw`). Guards against a session-end hook double-firing: if
the new text is a prefix of the most recent `raw/` entry, or vice
versa, the call is a no-op. Nothing consumes `raw/` until `consolidate
--plan` (ROADMAP.md 4.2). It is meant to be called by the session-end
path (ROADMAP.md 3.1), not typed by an agent during a lookup.

`lint` (ROADMAP.md 2.3, not built) enforces the writing conventions
below and is load-bearing, not cosmetic (CLAUDE.md gotcha 16): every
retrieval quality number this project has measured holds because page
summaries are information-dense, and that density is a writing-
discipline property, not a retrieval one.

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

## Scorecard against PLAN.md section 1

The three numbers the whole design serves, and what has actually been
measured (ROADMAP.md 1.9, `eval/agent_trial_1_9.md`):

| Target | Measured | Caveat |
|---|---|---|
| Session-start injection under 200 tokens | not measured | `.claude/skills/mf/SKILL.md` is ~8.3 KB, roughly 2,000 tokens per session that triggers it. At the lean call's ~118 tokens/lookup saving over raw, break-even is ~17 lookups per session. ROADMAP.md 2.11. |
| Under 1,200 tokens per lookup, most ending at the stub | 55 (lean call) / 1,014 (default flags) | In-vocabulary tasks only. Blind phrasing sends ~45% of lookups to `none` (section 3). |
| 2 tool calls per lookup | 1 (stub-end 20/20) | Same in-vocabulary caveat. |

## Known gaps

Things the code does that the docs used to describe differently, each
with the roadmap item that closes it:

- Embedding is instantiated in three places (`mf/search.py`,
  `mf/write.py`, `mf/indexer.py`), each loading a fresh `fastembed`
  model, and `_vec_literal` is copied into all three. `mf/embed_backend.py`
  (the MLX/fastembed selector) exists but only the eval harness uses it.
  This is exactly the single-source-of-truth drift the roadmap checklist's
  item 1 warns about. ROADMAP.md 2.9.
- `mf write` loads the model twice per call (once for the gate, once
  inside `index_field`). Same fix.
- `search` never checks a page's on-disk sha256 against the index before
  returning it, so PLAN.md section 3's "refuse on mismatch unless
  `--stale-ok`" is unbuilt. Flagged in ROADMAP.md 1.3, now 2.8.
- `bge-large-en-v1.5` is evaluated but not a selectable `mf init` model
  (`MODEL_REGISTRY` only wires nomic). ROADMAP.md 2.9.
- `claims.slug` has no definition: pages have no slug. ROADMAP.md 4.3.
- `DEFAULT_LIMIT`/`DEFAULT_NEIGHBOR_LIMIT` were chosen before the 1.9
  cost data and are wrong for the common case (CLAUDE.md gotcha 26).
  Left in place because 1.4's calibration ran at `limit=5`. ROADMAP.md
  2.7 revisits them alongside the recalibration.

## Stack

- Python for v1, distributed via `uv tool install`. `sqlite-vec` and
  FTS5 in-process, embeddings via `fastembed` (ONNX runtime), no model
  server. Each CLI call loads the model from scratch, which is the main
  latency cost of a lean `mf search`. A long-lived MCP server (ROADMAP.md
  5.1) would amortize it. Rust port only if install friction becomes
  the top complaint, and only after the schema stops changing (it is
  changing again in 2.5).
- Embedder: `nomic-embed-text-v1.5` (270 MB, 768-d, asymmetric
  `search_query:`/`search_document:` prefixes). M0.5 confirmed
  `bge-large-en-v1.5` is within noise of nomic on this corpus and
  costs ~1 GB more, so nomic stays the default (CLAUDE.md gotcha 3 on
  the prefix trap, gotcha 4 on running nomic and bge in separate
  processes). `mf/embed_backend.py` can select an MLX backend on Apple
  Silicon, but the CLI path is fastembed-only today.
- Reranker: none by default, see section 3 point 6.
- LLM: none. Extraction and consolidation are done by the host agent
  that's already running, the tool never calls an LLM itself.

## Where the open decisions are tracked

- Milestone list and scope per milestone: [PLAN.md](../PLAN.md) section 9.
- Current phase status and the Phase 2.5 hardening items: [ROADMAP.md](../ROADMAP.md).
- Numbered gotchas referenced above by number: [CLAUDE.md](../CLAUDE.md).
- Eval evidence behind the retrieval design: [M0.5_REPORT.md](../M0.5_REPORT.md).
- Confidence gate calibration methodology and full trade-off table:
  `eval/calibrate_confidence.py`. Blind re-test: `eval/blind_fallback_check.py`.
