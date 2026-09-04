# CLAUDE.md

The `mf` memoryfield CLI, its eval harness, and `notes/`, the field
this repo runs its own tool on. Context for the next agent, human or
model.

## What this repo is

`mf/` is the packaged CLI described in PLAN.md (`pyproject.toml`,
`uv tool install .`). Every Phase 1-3 command is real, plus the M5
partials `consolidate --plan` and `claim`. `eval/` is the eval and
corpus rig from M0/M0.5. The upstream memoryfield spec is vendored at
[docs/upstream/SPEC.md](docs/upstream/SPEC.md). mf builds on the
format, not on Cal's tool, and architecture.md section 6 records where
the two deliberately differ.

- CLI and flag reference: [docs/CLI.md](docs/CLI.md)
- Schema and retrieval design: [docs/architecture.md](docs/architecture.md)
- User-facing guides hub: [docs/README.md](docs/README.md)
- Eval numbers: [docs/M0.5_REPORT.md](docs/M0.5_REPORT.md) and
  [docs/BENCHMARKS.md](docs/BENCHMARKS.md). Never copy numbers from
  them into this file (gotcha 1).
- Decision trail, per-task records, and open debt (including 0.5's
  upstream frontmatter proposal, which needs a human to send it):
  [ROADMAP.md](ROADMAP.md). Milestone list: PLAN.md section 9.

`notes/` is a real mf field, this repo dogfooding its own tool. See
[notes/CLAUDE.md](notes/CLAUDE.md). `eval/corpus` pages are
calibration fixtures, never memory.

## Commands

Run from the repo root. `uv run ...` uses `.venv` and reflects source
changes immediately (gotcha 20).

```bash
uv run pytest tests/ -q                   # tests
ruff check mf/ eval/ tests/               # lint, gated in CI
npx --yes pyright <files>                 # typecheck, bare pyright is not on PATH
uv sync --group dev                       # tests + eval in one venv, add --extra mlx in the same call (gotcha 21)
uv run python3 eval/fetch_soapstones.py   # sha256-pinned interop fixture into gitignored eval/fixtures/, soapstones tests skip without it
```

Real-corpus smoke test: gotcha 29.

## Release

PyPI name is `memoryfield` (`mf` was taken). Console command, import
package, and module layout stay `mf`. Repo:
[github.com/whit3rabbit/memoryfield](https://github.com/whit3rabbit/memoryfield)
(singular, `memoryfields` in older commit messages is stale).

Cut a release: push to `main`, then `git tag vX.Y.Z && git push origin
vX.Y.Z`. `release.yml` builds, publishes via trusted-publisher OIDC
(the `pypi` environment is restricted to `v*` tags, no reviewers), and
cuts a GitHub release. The version lives once, in `mf/__init__.py`.
The PyPI trusted-publisher registration is already done.

CI (`test.yml`) runs pytest, ruff, and pyright with `uv sync --locked`,
`uvx ruff@0.16.5`, `npx pyright@1.1.409`, and bare `pyright` so
`pyrightconfig.json` is authoritative. Quirks:

- `astral-sh/setup-uv` publishes only exact tags (`@v10` 404s). Pin
  `@v10.0.1`-style and bump deliberately.
- The macOS leg installs Python via Homebrew with
  `UV_PYTHON_PREFERENCE: only-system`. uv-managed and
  `actions/setup-python` builds there lack
  `--enable-loadable-sqlite-extensions`, which `sqlite-vec` needs,
  even though a local Mac works. Environment gap, not a code bug.
- Deferred (ROADMAP.md): no tag/version assertion, no test gate before
  publish, and `upload-artifact@v7` against `download-artifact@v8`.

## Gotchas

Numbers are stable IDs cited from ROADMAP.md, docs/architecture.md,
and the reports. Gaps (12, 23, 28, 49, 50) are deleted or merged
records. The full trail behind each lives in ROADMAP.md under the
item it cites.

### Eval harness

1. Report prose must derive from computed values (`report.py`'s
   `avg()`/`val()`), never from hand-written claims. Hardcoded prose
   went stale once already.
2. Embedding bugs show only at retrieval, never at corpus level.
   Sanity-check one embedding's input text before trusting aggregate
   numbers.
3. fastembed adds the nomic query prefix implicitly but not BGE's.
   Re-check the prefix convention when swapping models.
4. Two fastembed `TextEmbedding` instances in one process can deadlock
   (`recursive_mutex lock failed`). Run models as separate processes.
5. `eval/baselines/dense_baseline.py` is the TF-IDF control.
   `dense_real_baseline.py` is the real embedder.
6. Top-k always returns k. No baseline abstains, so an empty-top-k
   check is not a no-answer metric.
7. Queries share an authoring process with the corpus, so in-vocabulary
   scores are a best case. The soapstones fixture (gotcha 29) is the
   only corpus outside it, and usable-answer rate drops to 0.75 there
   (BENCHMARKS.md 5).
8. De-biased stub labels ("stub has the answer") are more permissive
   than the original ("agent wouldn't need the body"). Lead with the
   de-biased one, PLAN.md section 6 depends on it (M0.5 report,
   spot-check section).
9. Subagent-generated labels (paraphrases, tags, de-bias judgments)
   cannot be regenerated identically. `eval/build_corpus.py`
   overwrites `eval/queries/*/queries.jsonl` on every run, so `git
   checkout` those files after regenerating the corpus.
10. Every single-baseline run overwrites `summary.json`. Rebuild it
    from the `metrics` entry of each
    `eval/results/{baseline}_{domain}.json`.
11. Never run the full baseline suite in the foreground (15 to 45
    minutes). Use the Bash tool's `run_in_background`, not manual
    `nohup`, so completion is tracked.
17. A computed metric nobody reads hides its own bugs
    (`stub_end_given_hit_rate` was silently 1.0 everywhere). If a
    field is not wired into the report, verify it directly.
18. Re-derive any "0% false positive" calibration result a second way
    before it becomes a constant. A scale mismatch once turned 13.3%
    into a clean 0%.
47. Never cache embeddings per script with a hardcoded model. Call
    `mf.embedder.embed_query`, which caches per `model_code` and
    follows the field's model.

### Retrieval and calibration

13. Ranking is dense-first since 2.6. FTS runs on every query as a
    gate signal and is the result set only when `vec` is empty.
    Earlier decisions: ROADMAP.md 1.5 and 2.6.
14. The vec table backs kNN neighbor stubs, write-time dedup, and the
    FTS-empty fallback. Only ranking was ever contested.
15. A raw bm25 floor cannot separate no-answer from real-answer
    queries. The gate is three-signal since 2.7. Trade-off table in
    `eval/calibrate_confidence.py`.
16. `lint` is required infrastructure. Every quality number depends
    on summary density, and density comes from writing discipline.
25. The "0% false-high-confidence" claim did not hold on blind
    phrasing (1.8). The dense fallback almost never fires, because
    OR-joined `fts_query()` nearly always finds some overlap. A larger
    blind no-answer sample is unclaimed follow-up.
26. Search defaults `--limit 2 --neighbor-limit 0` are a measured cost
    decision (ROADMAP.md 2.11). Only the lean call delivers PLAN.md
    section 6's savings. Measure content tokens with
    `eval/agent_trial_token_costs.py`, not the Agent tool's
    `subagent_tokens`.
27. The dedup gate (`DEDUP_THRESHOLD` = 0.10 cosine,
    `eval/calibrate_dedup.py`) catches copies and light rewordings,
    not thorough rewrites. About one in eight paraphrases passes.
    Check labeled negatives against the whole corpus, not only their
    anchor.
32. Eval and `mf/` must compute a calibrated constant the same way
    (cosine since schema v2). sqlite-vec
    returns NULL for a zero vector's cosine distance: guard for it,
    and never use zero base vectors in tests.
34. Report per-domain numbers. A codebase gap of 0.85 against 1.0 hid
    inside a two-domain average of 0.925.
35. When two eval tasks measure the same pipeline under different
    conditions, write the joint reading down. 1.8 and 1.9 each looked
    fine and together undercut the savings case.
36. Every retrieval constant so far was wrong on the next data set.
    Before hardcoding one, run `eval/calibrate_confidence_blind.py`
    (real `mf search`, blind queries, size sweep). Score the
    top-1 the tool presents. Keep its `os._exit(0)` (gotcha 4).
38. Default model `snowflake-arctic-embed-xs` (384-d), pinned per
    field by `mf init --model`. `mf model list` shows the registry.
    Open: `FLOOR`, `DENSE_FLOOR`, and `DEDUP_THRESHOLD` were calibrated
    on nomic and never re-swept on it (architecture.md "Known gaps").
44. Same prefix on both sides, too. `consolidate --plan` once compared
    query-prefixed vectors against a document-to-document threshold.
    Use `embedder.embed_document(s)`.
46. `_TOKEN_RE` once dropped digits and non-Latin scripts, so the
    `401`/`403` page was unreachable. Any tokenizer change gets the
    calibrate_confidence_blind A/B first
    (`eval/results/calibration_2026-09-03_audit.txt`).

### Page format and parsers

19. Test a new parser against the real corpus (gotcha 29) before
    trusting fixtures. `mf/page.py` passed its unit tests and rejected
    most real pages, with `mf index` reporting "0 upserted" and no
    reason.
39. mf's parser quotes ambiguous values before YAML sees them, so
    `title: API: the difference...` parses here and nowhere else
    (upstream's tool, Obsidian, `yaml.safe_load`). `mf lint` reports
    it as `spec-yaml`. Quote title, summary, and source.
43. That quoting shim is a parser of its own, and it once broke block
    scalars (`summary: |`). Feed it the real corpus and the spec's
    full value grammar as fixtures.

### Environment and tooling

20. Three Python environments coexist: system `python3`, `.venv`
    (`uv run`, reflects source immediately), and the global tool
    (`uv tool install --force .` to refresh). "Module not found" is
    usually the wrong environment.
21. `uv sync` resets the venv on each call. Put every `--extra` and
    `--group` in one invocation.
22. `pyrightconfig.json`'s `include` needs a manual entry for each
    new top-level package. A missing entry silently skips the
    directory.
24. Several Claude Code sessions can run against this repo.
    Check `git status` and mtimes before overwriting a changed file,
    and `git ls-files` before treating one as committed. Confirm
    commit scope when new work is entangled with pre-existing
    uncommitted changes.
33. `reads`, `co_read` links, and `claims` in `mf.sqlite3` come only
    from tool calls, so rebuilding the index loses them.
    `schema.migrate()` drops only derived tables and `mf index`
    rebuilds them. Keep it that way when bumping the schema.
37. **This repo is not a field. `notes/` is.** A root-level `mf init
    && mf index` silently indexes `eval/corpus`, because `_SKIP_DIRS`
    skips `raw` but not `eval`. Add `eval` there first if a root field
    is ever wanted.
40. MCP SDK v2: `from mcp.server import MCPServer`. The v1 `FastMCP`
    import is a stub that raises. Check the installed version
    (`mcp==2.1.1`) before trusting a sample.
41. hatchling's sdist bundles every tracked file unless scoped.
    `only-include = ["mf"]` fixes it. Verify any packaging change with
    `uv build && tar tzf dist/*.tar.gz`.
45. "Is the model downloaded?" must never instantiate the model
    (gotcha 4's deadlock). `mf/models.py` probes the cache directory.
    `get_embedder`'s cache fill is behind a lock because the MCP SDK
    runs tools on threads.
48. Tests are hermetic (no real model) except
    `tests/test_token_regression.py`. Document any new exception in
    its own docstring and in `conftest.py`'s.

### Patterns worth reusing

29. Real-corpus smoke test, cheaper than new fixtures. Clean up the
    tmpdir when done:

    ```bash
    tmpdir=$(mktemp -d) && cp eval/corpus/codebase/*.md "$tmpdir"/ && uv run python3 -m mf.cli init "$tmpdir" && uv run python3 -m mf.cli index "$tmpdir"
    ```

    Foreign field: swap the `cp` for `uv run python3 -m mf.cli unpack
    eval/fixtures/soapstones.memoryfield.zip "$tmpdir"` after
    `fetch_soapstones.py`.

30. New subcommand pattern: `mf/<verb>.py` with a dataclass result
    exposing `.as_dict()`, wired into `mf/cli.py` via `_cmd_<verb>()`,
    `_render_<verb>_text()`, and a subparser. Template: `mf/read.py`.
31. `vec0` KNN exposes a `distance` column (cosine since v2).
    `mf/search.py` never selects it, `mf/write.py`'s dedup gate does.
42. Measure a dependency's install cost before deciding core versus
    optional: `UV_TOOL_DIR=$(mktemp -d) uv tool install --force .`
    with and without it, then diff the package lists.

## Roadmap

M0 to M4 and M6 are closed. M5 (consolidation, multi-writer) is in
progress: `consolidate --plan`, `claim`, `contested`, and co_read
neighbor weighting (`MIN_CO_READ_WEIGHT` uncalibrated) are built.
Remaining: consolidate idempotency across runs, pointer-entry
expansion, and `write` auto-calling `claim`.

Phase 6 was a full audit
(schema v3, WAL, parser and tokenizer fixes, ROADMAP.md 6.1). M4
reopen trigger: rerank only if a later blind set drops the real
pipeline's top-1 under 0.8.
