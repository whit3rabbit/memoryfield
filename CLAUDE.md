# CLAUDE.md

The `mf` memoryfield CLI, its eval harness, and `notes/`, the field
this repo runs its own tool on. Context for the next agent, human or
model.

## What this repo is

The `mf` memoryfield tool described in PLAN.md, plus its eval harness.
`mf/` is a packaged CLI (`pyproject.toml`, `uv tool install .`). Every
Phase 1-3 command is real: `init`/`index`/`search`/`read`/`write`/
`raw add`/`lint`/`pack`/`unpack`/`model`/`hook`/`import`, plus the M5
partials `consolidate --plan` and `claim`. For the complete CLI
specification and flag reference, see [docs/CLI.md](docs/CLI.md). For
the schema and retrieval design as currently decided, see
[docs/architecture.md](docs/architecture.md). [docs/README.md](docs/README.md)
is the hub for the user-facing guides (agents, models, fields). `eval/` is the eval and
corpus rig from M0/M0.5, complete. The upstream memoryfield spec is
vendored at [docs/upstream/SPEC.md](docs/upstream/SPEC.md); mf builds
on the format, not on Cal's tool, and architecture.md section 6 is
the record of where the two deliberately differ.

`notes/` is a real mf field, this repo dogfooding its own tool:
`mf.sqlite3` at its root, Stop/SessionEnd hooks wired in
`notes/.claude/settings.json`, its own CLAUDE.md, and real `raw/`
entries for `consolidate --plan` to work against. `eval/corpus` pages
are calibration fixtures, never memory.

## Commands

Run from the repo root. `uv run ...` uses `.venv` and reflects source
changes immediately (gotcha 20).

- Tests: `uv run pytest tests/ -q`
- Lint: `ruff check mf/ eval/ tests/` (stable baseline of 7 `ISC004`
  findings, gotcha 23)
- Typecheck: `npx --yes pyright <files>` (bare `pyright` isn't on
  PATH)
- Tests + eval baselines in one venv: `uv sync --extra eval --group
  dev` in a single call (gotcha 21)
- Real-corpus smoke test: gotcha 29's recipe
- Interop fixture: `uv run python3 eval/fetch_soapstones.py` (sha256-pinned
  download into gitignored `eval/fixtures/`; the soapstones tests skip
  without it)

## Where things stand

The eval matrix is complete: 6 baselines (grep, FTS5, TF-IDF, nomic,
BGE-large, hybrid) times 2 domains (codebase, papers), 458 queries
(lexical, paraphrased, no-answer). Full numbers and the current
reading live in [docs/M0.5_REPORT.md](docs/M0.5_REPORT.md), generated
by `eval/report.py` from `eval/results/summary.json`. Every real
baseline except grep and TF-IDF clears 0.94 P@3: read that as the
query set being at ceiling, not as a verdict on which retriever wins
(gotcha 7). Don't hand-copy detailed numbers from the report into
this file. That duplication went stale before (gotcha 1).

A third domain exists since 2026-09-02: Cal Paterson's soapstones
export (95 real pages by other people's agents, fetched, never
committed) with 28 blind queries in `eval/queries/soapstones/`. It is
a stress test of the shipped pipeline, not a calibration set; the
numbers live in docs/BENCHMARKS.md section 5.

## Gotchas and lessons learned

Organized by where they will bite next. Numbers are stable IDs cited
from ROADMAP.md and the reports. Gaps (12, 28) are deleted records of
fixed bugs.

### Eval harness gotchas

1. **A report generator's hardcoded prose goes stale like a commit
   message.** `report.py`'s `substantive_findings()` claimed "FTS
   wins" after a bug fix flipped the numbers, right above a table
   proving otherwise. Prefer prose derived from computed values (its
   `avg()`/`val()` helpers) over hand-written claims.

2. **Embedding bugs don't show up at the corpus level, only at
   retrieval.** A one-line bug in the embedder input string silently
   cost 30 points of dense recall on one domain. Sanity-check a single
   embedding's text content before trusting aggregate numbers.

3. **fastembed does not add the BGE query prefix for you.** It adds
   the nomic prefix implicitly. BGE needs the same kind of asymmetric
   prefix, but fastembed treats it as symmetric. Re-check the prefix
   convention whenever you swap embedding models.

4. **fastembed's `TextEmbedding` is not thread-safe across two
   instantiations in one process.** Loading nomic and bge together can
   deadlock with `recursive_mutex lock failed`. Run them as separate
   process invocations instead, confirmed working by running
   `dense_bge` then `hybrid` as two sequential `run_baselines` calls.

5. **TF-IDF is not dense.** `eval/baselines/dense_baseline.py` is
   the TF-IDF control, not a real embedder. `dense_real_baseline.py` is
   the real one. A TF-IDF vs FTS comparison says nothing about dense.

6. **Top-k always returns k.** An empty-top-k check is not a real
   no-answer metric, since no baseline here has an abstention
   mechanism.

7. **The query set shares an authoring process with the corpus.**
   Pages were written, then queries to match them, then paraphrases
   from the queries. One vocabulary throughout, close to the best case
   any retriever will see. High scores are conditional on that and on
   the corpus's writing discipline, not portable to a sloppier corpus.
   The soapstones fixture is the one corpus outside that process, and
   the shipped gate's usable-answer rate drops from 0.85-0.90 to 0.75
   on it, mostly because its summaries repeat the title.

8. **De-biased stub labels use a more permissive bar than the original
   author labels.** Original: "agent wouldn't need the body" (67 to
   82%). De-biased: "stub has the answer" (99.1% of raw labels,
   corrected given-hit range 0.69-0.87, the number the report uses).
   Both are valid. Lead with the operational one, since PLAN.md
   section 6's token-savings model depends on it. A 20-sample blind
   spot-check agreed 18/20 (see the "Stub-sufficiency spot-check"
   section of docs/M0.5_REPORT.md).

### Process gotchas

9. **Subagent-generated labels can't be regenerated identically.**
   Paraphrases, topical/entity tags, and stub-end de-bias judgments came
   from background subagents at non-zero temperature. Paraphrase median
   Jaccard similarity to the original is 0.29 (max 0.50), so they're
   genuinely different wordings, not near-duplicates. Back up before
   regenerating. `eval/build_corpus.py` overwrites
   `eval/queries/*/queries.jsonl` on every run (it reproduces the corpus
   byte-identically, the queries not): `git checkout` both files after
   regenerating the corpus.

10. **`summary.json` gets overwritten on every single-baseline run.**
    `--baseline X --domain Y` writes only that one entry. To
    reconstruct the full summary, pull
    `json.loads(p.read_text())["metrics"]` from each
    `eval/results/{baseline}_{domain}.json` (each is a full trace dump
    with the summary entry nested under `metrics`) and write that list
    back as `summary.json`. Verified byte-identical against the
    committed original during the 1.1 restructure.

11. **Don't run the full baseline suite in the foreground.** It runs
    about 15 minutes for the fast baselines, 45 for BGE plus papers.
    Background it with the Bash tool's `run_in_background: true`, not
    manual `nohup ... &`: a manually-backgrounded process isn't
    tracked, so there's no completion notification.

### Plan-design gotchas (for M1 implementation)

13. **Record of the 1.5 ranking decision, superseded by 2.6 (gotcha
    36).** Symmetric RRF at equal weights had nothing to add once both
    signals were near ceiling, so 1.5 shipped FTS-first. Since 2.6,
    `mf/search.py` presents dense's top-k. FTS still runs on every
    query as a gate signal and is the result set only when `vec` is
    empty. Full decision trail in ROADMAP.md 1.5 and 2.6.

14. **The vec table backs three features, not one.** It backs kNN
    neighbor stubs, write-time dedup of paraphrased near-duplicates,
    and fallback ranking when FTS returns nothing. Only the ranking
    use was ever contested.

15. **Record of the 1.4 gate decision, superseded by 2.7 (gotcha
    36).** A floor on raw FTS bm25 score cannot separate no-answer
    from real-answer queries on this corpus: their score ranges
    overlap almost completely (gotcha 7's ceiling effect on a new
    axis). 1.4 used normalized bm25 plus FTS/dense top-1 agreement.
    The current gate is three-signal (ROADMAP.md 2.7). See
    `eval/calibrate_confidence.py` for the trade-off table and gotcha
    18 for a bug caught mid-calibration.

16. **`lint` is required infrastructure, not a nice-to-have.** Every
    quality number in this eval holds because page summaries are
    information-dense, and that density comes from writing discipline.
    If `lint` (PLAN.md section 5) isn't enforced, retrieval quality
    drifts, and the design verdicts change with it.

17. **A metric that's computed but never read hides its own bugs.**
    `stub_end_given_hit_rate` in `run_baselines.py` incremented its
    hit counter and denominator together on every retrieval hit, so it
    silently evaluated to exactly 1.0 across all 12 result files.
    Unnoticed, because `report.py` never consumed the field. If a
    computed field isn't wired into the report, verify it directly:
    "it's in the JSON" means neither "correct" nor "used".

18. **A "0% false-positive" calibration result is worth re-deriving
    before trusting it.** A scale mismatch in an early gap check made
    the check fire almost unconditionally and produced a clean-looking
    0% false-high at floor=1.5. The real number was 13.3%. Caught by
    re-deriving the same result a second way, not by code review. A
    surprising "it just works" calibration result gets checked twice
    before it becomes a hardcoded constant.

19. **A parser that only ever sees synthetic test fixtures will pass
    while rejecting most of the real corpus.** `mf/page.py`'s
    frontmatter parser passed all its unit tests, then rejected
    10-75+ pages per domain on the real 157-page corpus: this
    project's own `"Topic: specific question"` title convention (an
    unescaped `": "` in an unquoted value reads as a nested mapping)
    and any value starting with a backtick both fail plain-scalar
    YAML. `mf index` reported "0 upserted" with no indication why.
    Test new parsers against the real corpus (gotcha 29's recipe)
    before trusting hand-written fixtures.

### Environment / tooling gotchas

20. **Three different Python environments coexist for this repo:**
    system `python3`, the project `.venv` (`uv sync`), and the global
    tool install (`uv tool install .`). `uv run python3 -m mf.cli ...`
    uses `.venv` and reflects source changes immediately. The
    installed `mf` command does not, until you `uv tool install
    --force .` again. A "module not found" error is often just the
    wrong environment, not a missing dependency.

21. **`uv sync --extra X` and `uv sync --group Y` don't compose across
    separate calls**: each `uv sync` invocation resets the venv to
    exactly what that invocation specifies. Running eval baselines and
    the test suite together needs `uv sync --extra eval --group dev`
    in one call, not two sequential ones.

22. **`pyrightconfig.json`'s `include` list needs a manual update
    whenever a new top-level package appears** (`mf`, `eval`, `tests`
    so far). A missing entry doesn't error and silently skips
    type-checking that directory, so a clean `pyright` run can hide
    real problems in unlisted code.

23. **`ruff check mf/ eval/ tests/` has a stable baseline of 7
    pre-existing findings, all `ISC004` (implicit string concatenation)
    in `eval/report.py`'s hardcoded prose strings.** Compare the count
    after a change instead of re-diagnosing the same 7 every time, and
    don't fold fixing them into unrelated work.

24. **This repo can have more than one Claude Code session running
    against it at once.** Before assuming sole-writer state (especially
    on shared files like `pyproject.toml`, `README.md`, or
    `eval/run_baselines.py`), check `git status` and file mtimes. A
    file that changed on disk since you last read it may be another
    session's legitimate concurrent work, not corruption. Investigate
    before overwriting it.

### M1 calibration gotchas (surfaced by ROADMAP.md 1.8)

25. **Record of the 1.8 blind-set finding, re-measured and largely
    closed by 2.7 (gotcha 36).** The gate's "0% false-high-confidence"
    claim was calibrated against a no-answer set sharing the corpus's
    vocabulary and did not hold under blind phrasing: "GDPR deletion
    request process for customer data" (a genuine no-answer query)
    returned `confidence: high` pointing at `code-dm-soft-delete`, a
    topically-adjacent but wrong page, n=1/8. On the same set, the
    dense fallback essentially never fired, because `fts_query()`'s
    OR-joined tokenization almost always finds *some* lexical overlap,
    and the bm25-floor gate absorbed the degradation instead, demoting
    correct hits to `none` at roughly double the M0.5 rate. A larger
    blind no-answer sample is unclaimed follow-up. See ROADMAP.md 1.8
    and 2.7 for numbers and methodology.

26. **Search defaults are a measured cost decision, not a
    convenience.** Defaults are `--limit 2 --neighbor-limit 0`
    (ROADMAP.md 2.11 addendum, measured matrix in
    `eval/results/token_costs_2_11.txt`; 2.7's 3/1 pick was
    re-measured at 1.75x raw and dropped). The 1.9 real-agent trial
    (ROADMAP.md 1.9, `eval/agent_trial_1_9.md`) found the old
    defaults (`--limit 5 --neighbor-limit 3`) cost 1014 tokens/task,
    5.85x more than raw file exploration, while a lean call
    (`--limit 1 --neighbor-limit 0`) cost 55 tokens/task, 3.2x less:
    only the lean shape delivers PLAN.md section 6's modeled savings.
    The same trial: the Agent tool's `subagent_tokens` figure is
    useless for measuring this (~50k of per-agent-session overhead
    swamps the mechanism's few hundred tokens), so isolate content
    tokens directly (`eval/agent_trial_token_costs.py`). The skill
    teaches the lean call.

### M2 write-path gotchas

27. **The dedup gate catches copies and light rewordings, not thorough
    rewrites.** Calibrated by 2.10 on a 32-paraphrase labeled set
    (`DEDUP_THRESHOLD` = 0.10 cosine, `eval/calibrate_dedup.py`):
    paraphrase and genuinely-different distributions overlap, so about
    one in eight paraphrases passes at any threshold that spares real
    sibling pages, and a "sibling" written without seeing the corpus
    is as likely to duplicate some *other* existing page as to be a
    clean negative. Labeled negatives need checking against the whole
    corpus, not just their anchor. A second signal to catch thorough
    rewrites is not scheduled (docs/architecture.md records the
    limit).

### Phase 2 review gotchas

32. **Any constant calibrated in the eval harness and consumed in
    `mf/` must be computed the same way on both sides.** The nomic
    agreement numbers behind the gate were calibrated on cosine while
    the `vec0` table ran Euclidean L2 (fixed by 2.5, schema v2,
    cosine). Second-order rule from the fix: a zero vector has no
    cosine distance (sqlite-vec returns NULL), so the dedup gate needs
    a NULL guard and test fixtures must not use zero vectors as base
    vectors.

33. **Not everything in `mf.sqlite3` is derived from the pages.** The
    `reads` log, `co_read` rows in `links`, and `claims` accumulate
    from tool calls and have no other source, so "delete the index and
    rebuild" loses them. Upserts delete only the three typed link
    kinds, never `co_read`. A removed page drops its `co_read` rows in
    both directions.

34. **A per-domain gap can hide inside a two-domain average.** 1.8's
    blind-set headline reported FTS "flat" at 0.925, averaged across
    domains. The codebase domain alone was 0.85 against nomic's 1.0
    (MRR 0.79 vs 0.975, n=24). Report per-domain numbers whenever the
    two domains stress different retrievers (codebase pages are
    anchor-heavy, papers pages are prose-heavy).

35. **Two measurements that each look fine can be bad together.** 1.8
    found 45% of answerable blind queries returned `confidence: none`.
    1.9 found 100% stub-end at 55 tokens/lookup, on deliberately
    in-vocabulary tasks. Jointly: under realistic phrasing, about half
    of lookups paid for the search, were told not to cite the result,
    and fell back to raw exploration, undercutting PLAN.md section 6's
    savings case (2.7's gate recut moved usable blind answers to
    0.90/0.85). When two eval tasks measure the same pipeline under
    different conditions, write the joint reading down.

36. **Every retrieval decision so far was right on the data it had and
    wrong on the next set.** Ranking: the plan said RRF, M0.5 said
    FTS-first (both at ceiling, FTS cheaper), 2.6 measured through the
    real pipeline on blind phrasing and dense-first beat both on every
    cell, in-vocabulary included (RRF averages in FTS's noise). Gate:
    1.4 calibrated a bm25 floor on the in-vocabulary no-answer set,
    2.7 found it demoted 45% of blind answers and 80% of answers on a
    10-page field (bm25's IDF term shrinks with N). The fix each time
    was the same: run the *real* `mf search` code on a query set
    authored without seeing the corpus, and sweep corpus size, before
    hardcoding a constant. `eval/calibrate_confidence_blind.py` is the
    template: it now embeds through `mf.embedder` with the field's
    default model (`MF_CAL_MODEL` overrides) and takes domain names as
    arguments. Two pitfalls from writing it: score "usable answer" with
    the top-1 the tool actually *presents* (the FTS-scored and
    dense-scored numbers differ on every low-confidence query), and
    fastembed/onnxruntime aborts with `recursive_mutex lock failed` at
    interpreter exit when a module-level model is torn down (gotcha
    4's family), so the script flushes and `os._exit(0)`s.

### Phase 4 dogfooding gotchas

37. **This repo is not itself a field. `notes/` is.** A root-level
    `mf init && mf index` here would silently sweep
    `eval/corpus/{codebase,papers}` (157 real frontmattered pages of
    calibration fixtures) into the field, because `_SKIP_DIRS`
    excludes `raw` but not `eval`. Same silent-failure family as
    gotchas 17 and 19: nothing errors, the wrong data quietly becomes
    the corpus. If a root-level field is ever wanted, `eval` needs a
    `_SKIP_DIRS` entry first.

38. **Embedding model selection and dimension pinning
    (`snowflake-arctic-embed-xs`).** `MODEL_REGISTRY`
    (`mf/embedder.py`) defaults to `snowflake-arctic-embed-xs`
    (384-d, ~170 MB), which benchmarked at 0.950 average blind Top-1
    with a 33 ms cached load time (5.6x faster than Nomic v1.5) and
    0.9 ms query latency, cutting vector DB storage in half.
    `MODEL_REGISTRY` also supports `snowflake-arctic-embed-s` (384-d),
    `bge-small-en-v1.5` (384-d), `bge-base-en-v1.5` (768-d),
    `bge-large-en-v1.5` (1024-d), `nomic-embed-text-v1.5` (768-d),
    `all-MiniLM-L6-v2` (384-d), and `jina-embeddings-v2-small-en`
    (512-d). `mf model list` prints the table of models, speeds,
    sizes, and cache status; `mf model install <name>` downloads and
    warms a model ahead of time. When initializing a field,
    `mf init --model <name>` pins the model and dimension into
    `config`. Full benchmarks live in
    [docs/BENCHMARKS.md](docs/BENCHMARKS.md). Open: `FLOOR`,
    `DENSE_FLOOR`, and `DEDUP_THRESHOLD` were calibrated on nomic
    distances (2.7, 2.10) and have not been re-swept on the arctic-xs
    default; the soapstones run is the only measurement of the shipped
    gate on it (docs/architecture.md "Known gaps").

39. **mf's frontmatter parser is more lenient than every other reader,
    and that leniency hid a 100% interop failure.** `mf/page.py` quotes
    ambiguous values before YAML sees them, so `title: API: the
    difference between 401 and 403` (this project's own convention) and
    a backtick-leading summary parse here and nowhere else: upstream's
    tool, Obsidian, and any plain `yaml.safe_load` reject them
    (`ScannerError`). 157/157 eval corpus pages failed that way until
    `eval/build_corpus.py` quoted title/summary/source (2026-09-02),
    and the skill's reference.md used to say the unquoted form "is
    fine". `mf lint` reports it as `spec-yaml`. Same family as gotcha
    19, from the other side: a parser that accepts more than the format
    lets pages drift out of the format without anyone noticing. The
    spec itself is vendored at docs/upstream/SPEC.md, and Cal's real
    95-page export (`eval/fetch_soapstones.py`) is the fixture that
    caught this.

### Phase 5 packaging gotchas

40. **MCP Python SDK v2 renamed `FastMCP` to `MCPServer` and moved the
    import path.** `from mcp.server.fastmcp import FastMCP` (the
    widely-documented v1 API) is a stub in `mcp>=2` that raises
    `ModuleNotFoundError` pointing at a migration guide, not a working
    import. Use `from mcp.server import MCPServer` (`mf/mcp_server.py`,
    ROADMAP.md 5.1). Confirm the installed SDK version (`mcp==2.1.1`
    here) before trusting any mcp code sample, training-data or
    otherwise.

41. **hatchling's default sdist bundles every git-tracked file:**
    `uv build` shipped the full eval corpus, every doc, and this
    repo's own private `notes/raw/` session extracts into the source
    distribution, since no `[tool.hatch.build.targets.sdist]` config
    existed to scope it (the wheel was already scoped via `packages =
    ["mf"]`). Same silent-failure family as gotcha 37. Fixed with
    `only-include = ["mf"]` (ROADMAP.md 5.2); verify any future
    packaging change with `uv build && tar tzf dist/*.tar.gz`.

### Tooling patterns worth reusing

29. **Quick real-corpus smoke test, cheaper than writing new
    fixtures:** `tmpdir=$(mktemp -d) && cp eval/corpus/codebase/*.md
    "$tmpdir"/ && uv run python3 -m mf.cli init "$tmpdir" && uv run
    python3 -m mf.cli index "$tmpdir"`: catches gotcha-19-style
    parser/behavior bugs synthetic fixtures miss. It caught real bugs
    in 1.6, 1.8, 2.1, and 2.2. Clean up the tmpdir when done. For a
    field this project did not write, swap the `cp` for `uv run
    python3 -m mf.cli unpack eval/fixtures/soapstones.memoryfield.zip
    "$tmpdir"` after `eval/fetch_soapstones.py`; it caught gotcha 39.

30. **New `mf` subcommand pattern**, established by `read`, `write`,
    `raw add`, `claim`, and `consolidate`: one module `mf/<verb>.py`
    with a dataclass result type exposing `.as_dict()`, wired into
    `mf/cli.py` via `_cmd_<verb>()` + `_render_<verb>_text()` + an
    argparse subparser. Follow `mf/read.py` or `mf/write.py` as the
    template for the next one.

31. **sqlite-vec's `vec0` KNN queries expose a `distance` column**
    (`SELECT page_uuid, distance FROM vec WHERE embedding MATCH ? AND
    k = ?`), L2 by library default, cosine in this schema since v2.
    `mf/search.py` never selects it, since ranking only needs the uuid
    order. `mf/write.py`'s dedup gate does: it needs the actual
    distance to compare against `DEDUP_THRESHOLD`. Worth knowing
    before assuming it's unavailable.

42. **Measure a dependency's real install cost before deciding core
    vs optional:** build twice into a scratch tool dir
    (`UV_TOOL_DIR=$(mktemp -d) uv tool install --force .`), once with
    and once without the dependency, and diff the installed package
    lists. Caught that `mcp` pulled in 14 packages (`cryptography`,
    `starlette`, `uvicorn`, and their own trees) nothing in the core
    CLI touches, moved to the `mcp` extra instead of shipping as a
    hard dependency (ROADMAP.md 5.2).

## Roadmap

M0 through M4 are closed (eval matrix, read path, write path,
hooks/imports, reranker cut). M5, consolidation and multi-writer, is
in progress: `consolidate --plan`, `claim`, `contested` status, and
the `notes/` dogfooding field are built, and 4.4 (co_read weighting
in neighbor ranking, `MIN_CO_READ_WEIGHT` uncalibrated) landed
2026-09-02. Remaining: consolidate idempotency across runs,
pointer-entry expansion, and `write` auto-calling `claim`. M6, the
MCP server (5.1) and packaging polish (5.2), landed 2026-09-02. Full
task detail, per-task decision records, and open debt
(including 0.5's upstream frontmatter proposal, which now has a
destination and still needs a human to send it) in
[ROADMAP.md](ROADMAP.md).
The milestone list is PLAN.md section 9.

M4 reopen trigger: rerank only if a later blind set drops the real
pipeline's top-1 under 0.8. Not triggered by the first foreign
field (soapstones, 2026-09-02: dense-first blind top-1 0.90,
docs/BENCHMARKS.md section 5).
