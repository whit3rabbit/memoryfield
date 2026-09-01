# mf: architecture reference

Standalone reference for the schema and retrieval design. Full rationale
and the "why" behind each stack choice lives in [PLAN.md](../PLAN.md).
The evidence behind each retrieval decision lives in
[M0.5_REPORT.md](../M0.5_REPORT.md). This doc states what the design
currently is, not why it got there. Where the built thing and the
intended thing differ, both are stated and the roadmap item that closes
the gap is named.

## Layers

Six layers. The first is the spec, the rest are derived or conventional.

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
reads   (id, uuid, section, tier, read_at, call_id) -- append-only log written by `mf read`
```

**What is and isn't rebuildable.** `pages`, `sections`, `fts`, `vec`,
and the three typed link kinds are derived from the files and come back
identical from `mf index`. Three things are not: the `reads` log,
`co_read` rows in `links`, and `claims`. They accumulate from tool calls
and have no other source, so deleting `mf.sqlite3` loses them. `mf
index` preserves `co_read` across page edits and drops it only when the
page's file is gone (fixed during the Phase 2 review, it used to wipe
it on every upsert). `reads.call_id` groups the rows of one `mf read`
call (schema v2), so `co_read` is rebuildable from `reads` alone: every
pair of distinct uuids sharing a `call_id` is one increment. Nothing
runs that rebuild yet.

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
fixed vector width), `schema_version` to `2`. Set once by `mf init`,
read by `mf index`/`mf search` on every call. Model identity lives here,
at the index level, not per `vec` row. `open_field()` refuses an index
whose `schema_version` doesn't match and says to delete it and rerun
`mf init` + `mf index`: there is no in-place migration, because a
`vec0` table can't change metric and the index is derived anyway.

**Distance metric: cosine (schema v2, ROADMAP.md 2.5).** `vec` is a
`vec0` table declared `distance_metric=cosine`, so every distance the
tool computes (kNN neighbor order, the FTS/dense agreement signal, the
dedup threshold) is `1 - cos`, range 0 to 2, and matches what the eval
baselines and gate calibration compute. Schema v1 used `vec0`'s default
Euclidean L2 over raw fastembed output, and the nomic vectors are not
unit-normalized (norm around 20, measured), so v1 distances mixed vector
magnitude into all three. That was a calibration/production mismatch of
the same shape as CLAUDE.md gotcha 18 (see gotcha 32).

The `vec` table backs three separate features, not one (CLAUDE.md
gotcha 14): kNN neighbor stubs, write-time dedup of near-duplicate
pages, and fallback ranking when FTS returns nothing.

### 3. Retrieval

`search` (`mf/search.py`) runs **dense first: the result set is dense's
top-k by cosine distance. FTS runs on every query too, but as a gate
signal, not a ranking.** This is the third ranking design (ROADMAP.md
2.6). The plan said symmetric RRF. M0.5 picked FTS-first because both
signals were at ceiling on the in-vocabulary set and FTS needed no
model (CLAUDE.md gotcha 13). 1.4 then made dense run on every query for
the gate, which killed the cost argument, and the blind set (1.8) was
the first data where the two diverged. 2.6 measured all three through
the real pipeline on the cosine `vec` table
(`eval/calibrate_confidence_blind.py`, top-1 accuracy of the presented
result):

| Ranking | codebase, original (n=174) | codebase, blind (n=20) | papers, original (n=254) | papers, blind (n=20) |
|---|---|---|---|---|
| FTS-first (1.5 design) | 0.828 | 0.700 | 0.882 | 0.800 |
| RRF, k=60 (plan) | 0.862 | 0.800 | 0.917 | 0.850 |
| **dense-first** | **0.925** | **0.950** | **0.921** | **0.900** |

Dense wins every cell, in-vocabulary included. RRF loses to dense-first
because it averages in FTS's noise. Inserting FTS's top-1 at rank 2
under dense moved MRR by under 0.01 either way and was not adopted.

1. Results return as the top-k stubs (uuid, title, summary, status,
   tokens; `k=3` by default, `mf search --limit`) with up to n neighbor
   stubs each (`n=1` by default, `--neighbor-limit`, typed links first,
   then kNN). The old defaults (5 / 3) cost 1,014 tokens per point
   lookup (ROADMAP.md 1.9). 3 / 1 is the compromise: three stubs recover
   from a wrong top-1, one neighbor slot surfaces a typed
   `supersedes`/`contradicts` link, which an agent must not miss.
   `co_read` rows accumulate from `mf read` but are not consulted for
   neighbor ranking yet (ROADMAP.md 4.4).
2. FTS's ranked list is the result set only when dense has nothing (an
   empty `vec` table). A stopword-only query (empty FTS expression) is
   still ranked by dense.
3. A superseded page never occupies a result slot (ROADMAP.md 2.8). A
   hit on it resolves to the page that supersedes it, following the
   chain, and that stub carries `supersedes: [old, ...]`. Two hits that
   resolve to one superseder share one slot. The same resolution runs
   for neighbors, so a superseded page never shows as a neighbor of its
   own replacement. The 1.5 design returned a `{uuid, superseded_by}`
   pointer in the slot, which under `--limit 1` meant no answer.
5. Stale check (PLAN.md section 3). `mf search` compares each shown
   page's on-disk sha256 to the index (a missing file counts as stale).
   Any mismatch is refused with exit code 3 and a "run `mf index`"
   message, unless `--stale-ok`, which returns the results with the
   affected stubs marked `stale`. Library callers opt in by passing
   `field_dir`.
4. Reranker (cross-encoder over the top 20): the tool's own blind top-1
   is now 0.95 / 0.90 through the real pipeline, above the ~0.8 trigger
   in ROADMAP.md 4.1. Cut, not deferred, unless a later blind set says
   otherwise.

Output is JSON or a compact text table. The agent never sees a body
unless it asks.

**Confidence gate: three signals, recalibrated on blind phrasing
(ROADMAP.md 2.7).** `mf/confidence.py` computes
`confidence: high|low|none`:

- **not-none** if any of: normalized bm25 (FTS top score / matched-term
  count) at or above `FLOOR` (2.0), dense top-1 cosine distance at or
  below `DENSE_FLOOR` (0.30), or FTS and dense agree on top-1.
- **high** if agreement *and* the dense floor both pass, else **low**.

The 1.4 design used the bm25 floor alone for none vs. not-none, and
agreement alone for high vs. low. The blind sets showed two failures:
45% of answerable blind queries came back `none` (and the skill says
not to cite `none`), and bm25's IDF term shrinks with corpus size, so a
10-page field returned `none` for 80% of correct answers. Real fields
start small. The dense floor is size-independent and the agreement
rescue costs nothing in false-high. Measured through the real pipeline
(`eval/calibrate_confidence_blind.py`; "usable" = presented top-1
correct and confidence not `none`; no-answer sets are the original 30
plus 48 blind ones authored without seeing the corpus):

| Measurement | codebase, original | codebase, blind | papers, original | papers, blind |
|---|---|---|---|---|
| Usable answers, 1.4 gate | 0.667 | 0.550 | 0.728 | 0.550 |
| **Usable answers, 2.7 gate** | **0.920** | **0.900** | **0.913** | **0.850** |
| False-high on no-answer queries | 0/17 | 1/24 | 0/13 | 0/24 |
| No-answer queries returned as `low` | 5/17 | 4/24 | 2/13 | 4/24 |
| Usable answers on a 10-page subsample, 1.4 gate | 0.185 | | 0.300 | |
| Usable answers on a 10-page subsample, 2.7 gate | 0.889 | | 1.000 | |

The cost is the `low` row: a no-answer query gets a topically-adjacent
page labelled `low` 15-30% of the time instead of `none`. `low` means
"a lead, not an answer" (SKILL.md), which is the right label for that
page. The one blind false-high is the GDPR query from 1.8 (CLAUDE.md
gotcha 25), which both retrievers still land on. The full parameter
grid is in the calibration script.

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

**Built (ROADMAP.md 2.1, reshaped by 2.8).** `mf/write.py`, wired into
`mf/cli.py`: `write <path> [--field DIR] [--dest NAME] [--update UUID]
[--force] [--json]`. The draft can be a path outside the field, a path
inside it, or `-` for stdin (which needs `--dest`). It parses via the
same parser `index` uses (raises on missing `uuid`/`title`), checks the
destination (an existing file there must carry the same uuid, and the
uuid must not already be indexed under another filename), then runs
the dedup gate: embeds the page (`document_text()`) and kNN-queries
`vec` for existing pages within `DEDUP_THRESHOLD` (0.10 cosine
distance, section 2), excluding the page's own uuid. A hit returns the
candidates and exit code 2. `--update UUID` (must match the page's own
`uuid`) or `--force` skip the gate. On a pass, a draft from outside the
field is copied to `field/<dest>` (default: the draft's own filename)
and **only that page** is indexed (`indexer.index_page()`); the draft
itself is left where it was.

Why the draft belongs outside the field: the gate can only refuse to
index. A blocked draft that already sits inside the field is still a
`.md` with valid frontmatter, so the next `mf index` indexes it with no
check at all. That was how 2.1 shipped, and it made the gate advisory.
An in-field path still works (validated and indexed in place), but a
block on one returns a warning saying exactly that. `mf index` remains
the deliberately un-gated bulk path (imports, hand edits). Verified on
the real corpus: a paraphrase draft outside the field was blocked at
distance 0.049 with nothing copied in.

`DEDUP_THRESHOLD` (0.10) is calibrated on a labeled set (ROADMAP.md
2.10, `eval/calibrate_dedup.py`, `eval/dedup_set/`): 32 paraphrases of
real pages written by subagents given only the anchor (same facts, new
wording, restructured), 32 "sibling" pages on the same topic, and the
157 corpus pages' own nearest genuinely-different neighbors.

| Cosine distance | min | median | p90 | max |
|---|---|---|---|---|
| Paraphrase to its original (n=32) | 0.026 | 0.054 | 0.114 | 0.147 |
| Corpus page to nearest different page (n=157) | 0.096 | 0.207 | | |

| Threshold | Paraphrases missed | Corpus pages blocked on write |
|---|---|---|
| 0.08 | 7/32 | 0/157 |
| **0.10** | **4/32** | **2/157** |
| 0.12 | 2/32 | 5/157 |

The distributions overlap, so no threshold catches every rewrite
without blocking real pages. The blocked corpus pairs are one-claim-
per-paper siblings (RoPE definition vs its relative-position property,
three distillation pages), the page style PLAN.md section 7 prescribes.
A miss is a silent duplicate; a block is one look at the listed
candidates and `--force`. So the threshold errs toward blocking, at
0.10 rather than 0.12 because the papers style would pay for 0.12 on
3% of its pages. The sibling pages turned out not to be usable
negatives: the five closest all duplicated a *different* existing page
(the authors picked questions the corpus already answered), which the
gate correctly blocked. What this says about the gate: cosine on title
+ summary + L1 catches copies and light rewordings, not thorough
rewrites, one in eight of which pass. A second signal (title/summary
lexical overlap, or the host agent's judgment on the candidates) is
what would close that, and is not scheduled.

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

**`lint` built (ROADMAP.md 2.3).** `mf/lint.py`, `mf lint [DIR]
[--check] [--all] [--json]`. It enforces the writing conventions below
and is load-bearing, not cosmetic (CLAUDE.md gotcha 16): every retrieval
quality number this project has measured holds because page summaries
are information-dense, and that density is a writing-discipline
property, not a retrieval one. It checks shape, not quality (PLAN.md
section 10). Three severities: `error` (the page will misbehave:
duplicate uuid, missing summary, dangling typed link, bad status, over
8 KB), `warning` (a convention the eval depends on: summary shaped as
a topic or shorter than five words, a table, a copied SHA or relative
time, headed sections in a page under 300 tokens with `## Don't`
excepted, `active` but superseded, `superseded` but unlinked, and index
drift: stale, unindexed, or missing-file pages when `mf.sqlite3`
exists), `info` (advice: missing `source`, no typed links, a negation
in prose with no `## Don't` section, a page under 100 tokens). `--check`
exits 1 on any error or warning; info prints only with `--all`.
Baseline on the eval corpus: codebase 0 errors, 3 warnings (two
relative-time phrases, one two-section short page); papers 0 and 0.

### 6. Pack

**Built (ROADMAP.md 2.4).** `mf/pack.py`: `pack [DIR] [--out PATH]
[--no-index] [--no-raw]` and `unpack ZIP [DEST] [--sha256 HEX]
[--force]`. The archive root mirrors the field root: pages keep their
relative paths, `raw/` and `mf.sqlite3` are included by default, and
everything `mf index` skips is left out. A sidecar
`<name>.memoryfield.zip.sha256` holds the digest in `sha256sum` form.
Members are written sorted with a fixed timestamp, so the archive is
reproducible: same content, same digest. `unpack` verifies the digest
(sidecar or `--sha256`) before extracting (exit 2 on mismatch), refuses
member paths that escape the destination, refuses a non-empty
destination unless `--force`, strips a single top-level directory when
every member sits under one (a folder zipped from a file manager), and
reports how many pages disagree with the packed index. The extracted
index works as-is because `pages.filename` is field-relative; a
spec-plain field (four spec fields, no index) unpacks and then needs
`mf init` + `mf index`.

What is not verified: the memoryfield spec's own zip layout. No copy of
it exists in this repo (the same gap that blocks ROADMAP.md 0.5), so
"root mirrors field, plus a folder-zipped variant" is a stated
assumption, and compatibility with a real spec archive is untested.

## Writing conventions (enforced by `lint`, taught by the skill)

- `summary` is the answer: "Integration tests: `make test-integration`;
  needs `DATABASE_URL`", not "Notes on testing."
- First section answers, and rationale and history follow.
- Up to 800 tokens per page, 8 KB ceiling. PLAN.md section 5 says
  300-800, but not one of the eval corpus's 157 pages reaches 300 (they
  average ~240) and every retrieval number was measured on them, so
  `lint` treats 300 as the headers cutoff, not a floor.
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
| Session-start injection under 200 tokens | ~100 (skill description) | Only the skill's frontmatter description loads at session start. The body loads when the skill triggers: ~2,400 tokens before 2.11, ~730 after, with ~1,300 more in `reference.md` read only when writing a page. Estimated with `mf.tokens.default_tokenize`. |
| Under 1,200 tokens per lookup, most ending at the stub | 55 (lean call) / 1,014 (old default flags) | In-vocabulary tasks. The 2.7 gate cuts blind `none` from 45% to 10%; the new default (3 / 1) hasn't been re-measured with the 1.9 method (ROADMAP.md 2.11). |
| 2 tool calls per lookup | 1 (stub-end 20/20) | Same in-vocabulary caveat. |

## Known gaps

Things the code does that the docs used to describe differently, each
with the roadmap item that closes it:

- `claims.slug` has no definition: pages have no slug. ROADMAP.md 4.3.
- `DEFAULT_LIMIT`/`DEFAULT_NEIGHBOR_LIMIT` moved from 5 / 3 to 3 / 1
  with 2.7 (CLAUDE.md gotcha 26). The token cost of the new default
  hasn't been re-measured with the 1.9 method. ROADMAP.md 2.11.

## Stack

- Python for v1, distributed via `uv tool install`. `sqlite-vec` and
  FTS5 in-process, embeddings via `fastembed` (ONNX runtime), no model
  server. Each CLI call loads the model from scratch, which is the main
  latency cost of a lean `mf search`. A long-lived MCP server (ROADMAP.md
  5.1) would amortize it. Rust port only if install friction becomes
  the top complaint, and only after the schema stops changing (v2
  landed with 2.5).
- Embedder: `nomic-embed-text-v1.5` (270 MB, 768-d, asymmetric
  `search_query:`/`search_document:` prefixes). M0.5 confirmed
  `bge-large-en-v1.5` is within noise of nomic on this corpus and
  costs ~1 GB more, so nomic stays the default (CLAUDE.md gotcha 3 on
  the prefix trap, gotcha 4 on running nomic and bge in separate
  processes). `mf init --model bge-large-en-v1.5` builds a 1024-d field
  with it (2.9); the model is fixed per field. All three commands embed
  through `mf/embedder.py`, which owns the model registry, a per-process
  model cache (so `mf write` loads once for gate and index), and
  `vec_literal()`. Backend is fastembed unless `MF_EMBED_BACKEND=mlx`;
  not auto-selected, because an index's vectors must come from one
  runtime and the backend isn't recorded in `config`. Caveat: `FLOOR`,
  `DENSE_FLOOR`, and `DEDUP_THRESHOLD` were calibrated on nomic
  distances; a bge field runs on those constants uncalibrated (bge's
  cosine distances sit in a different range). Recalibrate before
  trusting a bge field's `confidence`.
- Reranker: none, see section 3 point 4.
- LLM: none. Extraction and consolidation are done by the host agent
  that's already running, the tool never calls an LLM itself.

## Where the open decisions are tracked

- Milestone list and scope per milestone: [PLAN.md](../PLAN.md) section 9.
- Current phase status and the Phase 2.5 hardening items: [ROADMAP.md](../ROADMAP.md).
- Numbered gotchas referenced above by number: [CLAUDE.md](../CLAUDE.md).
- Eval evidence behind the retrieval design: [M0.5_REPORT.md](../M0.5_REPORT.md).
- Confidence gate and ranking calibration, full parameter grid and
  corpus-size sweep: `eval/calibrate_confidence_blind.py` (2.7). The
  1.4 calibration (`eval/calibrate_confidence.py`) and 1.8 re-test
  (`eval/blind_fallback_check.py`) are kept as the record.
