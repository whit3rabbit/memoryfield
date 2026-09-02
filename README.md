# memoryfields

Based on: https://calpaterson.com/memoryfields.html

mf is a search-first memory tool for coding agents. A field is a
directory of Markdown pages with frontmatter, and mf indexes it into
SQLite with full-text and vector search.

A lookup returns stubs, not pages. The agent reads a summary first and
opens the body only when it needs it. The tool never calls an LLM, and
the pages stay plain Markdown you can read, diff, and edit.

Session-injected memory costs the same on every task, whether or not it
gets used. mf moves that cost to lookup time: about 100 tokens for a
default search, about 55 for a point lookup (measured over 20 real
agent tasks, ROADMAP.md 1.9).

Most lookups end at the stub.

## Install

Python 3.11 or newer, installed through [uv](https://docs.astral.sh/uv/):

```bash
uv tool install .                        # from a checkout
uv tool install git+https://github.com/whit3rabbit/memoryfields
```

The first search downloads the embedding model (default:
snowflake-arctic-embed-xs, 384-d, ~170 MB). The model is pinned per
field at `mf init` time. Pass `--model <name>` to `init` for other
models (e.g. `bge-small-en-v1.5`, `nomic-embed-text-v1.5`, `bge-large-en-v1.5`).

## Quickstart

Using this repo's eval corpus as sample pages:

```console
$ mf init ~/field
Initialized empty field at ~/field/mf.sqlite3 (model snowflake-arctic-embed-xs, 384-d)

$ cp eval/corpus/codebase/*.md ~/field/ && mf index ~/field
75 upserted, 0 unchanged, 0 deleted

$ mf search "how do we roll back a deploy" --field ~/field
confidence: low
- [code-deploy-rollback-cmd] Deploy: how to roll back a bad release
    `kubectl rollout undo deployment/<service>`; rollback is a forward operation and takes ~90 seconds end-to-end.
- [code-deploy-pre-checklist] Deploy: pre-deploy checklist
    Tests green, migrations applied to staging, dashboards reviewed, on-call notified, rollback plan documented.
```

Read the confidence line before the results:

- `high`: the stub is safe to cite.
- `low`: a strong lead. `mf read <uuid>` for the page's answer section
  before quoting it.
- `none`: do not cite it.

The gate errs toward demotion, not overclaiming.

When the stub is not enough, reads tier up: `mf read <uuid>` returns
the answer section (L1), and `--tier L2` or `<uuid>#section` returns
more.

Batch reads for one task into a single `mf read a b` call, since that
is what records which pages get used together. Widen a search
(`--limit 3`, `--neighbor-limit 1`) only when the confidence is low or
the question is genuinely broad.

New pages go in through `mf write <draft> --field <dir>`, drafting
outside the field. It validates, dedup-checks against near-duplicates,
copies the page in, and indexes it in one step.

Exit 2 means a near-duplicate was flagged: update that page
(`--update <uuid>`) or `--force` if the page really is new. Retire a
page by writing its replacement with `supersedes: [old-uuid]`, not by
deleting the file.

## Design decisions

Every retrieval and schema choice in `mf` is backed by empirical benchmarks across a 157-page corpus, 458 queries, and blind phrasing sets (details in [docs/architecture.md](docs/architecture.md) and [docs/M0.5_REPORT.md](docs/M0.5_REPORT.md)):

- **Dense-first ranking over RRF and FTS**: The original design planned symmetric RRF, and early versions used FTS-first. When benchmarked through the real pipeline on blind vocabulary-mismatch queries (`eval/calibrate_confidence_blind.py`), dense-first significantly outperformed both:
  - Codebase blind top-1: **0.950** (dense-first) vs. 0.800 (RRF) vs. 0.700 (FTS-first).
  - Papers blind top-1: **0.900** (dense-first) vs. 0.850 (RRF) vs. 0.800 (FTS-first).
  RRF diluted ranking quality by averaging in FTS keyword noise. FTS is retained on every query as a confidence signal and fallback, not as the primary ranker.
- **Calibrated multi-signal confidence gate**: Early confidence scoring relied solely on BM25 score floors. Blind testing revealed two major flaws: 45% of answerable blind queries returned `none`, and BM25's IDF term collapsed on small fields (an 80% `none` failure rate on 10-page fields). The gate was redesigned to combine dense floor distance (`<= 0.30`), BM25 score, and top-1 agreement:
  - Usable answers jumped from **0.550 -> 0.900** on blind queries and **0.185 -> 0.889** on 10-page field subsamples.
  - False-high citations remained near zero (0/17 original, 1/24 blind).
- **Cosine distance over Euclidean L2 (`vec0`)**: Nomic embedding vectors are not unit-normalized (norm ~20). Using default Euclidean L2 mixed vector magnitude into distances. Declaring `distance_metric=cosine` in SQLite schema v2 aligned distance calculations (`1 - cos`) across kNN neighbors, dedup thresholds, and confidence calibration.
- **Lean stubs by default (`--limit 2 --neighbor-limit 0`)**: Task-based token cost measurements across 20 real agent sessions (`eval/results/token_costs_2_11.txt`) showed the original 5 stubs / 3 neighbors cost 1,009 tokens per lookup (5.8x a raw read). Dropping to 2 stubs / 0 neighbors cut the cost to **104 tokens per lookup** (55 tokens for `--limit 1`), while keeping the target answer visible on screen in every trial. Two stubs preserve a single fallback slot for a wrong top-1.
- **Write-time dedup gate (`DEDUP_THRESHOLD = 0.10`)**: Calibrated against 32 subagent-authored paraphrases and 157 corpus pages (`eval/calibrate_dedup.py`). A 0.10 cosine distance threshold on `title + summary + L1` catches 88% (28/32) of duplicate rewrites while blocking only 2/157 valid sibling pages (avoiding the 3% false-block rate of 0.12). Drafts are checked outside the field before copying to prevent un-gated indexing on subsequent runs.
- **Ultra-lightweight default embedder (`snowflake-arctic-embed-xs`)**: Benchmarks across the 157-page corpus ([docs/BENCHMARKS.md](docs/BENCHMARKS.md)) show `snowflake-arctic-embed-xs` achieves **0.950 average blind Top-1** with **33 ms cached load time**, **0.9 ms query latency**, and 50% less vector storage than 768-d models (384-d vs 768-d). Alternative models like `bge-small-en-v1.5`, `nomic-embed-text-v1.5`, `bge-large-en-v1.5`, `all-MiniLM-L6-v2`, and `jina-embeddings-v2-small-en` are selectable via `mf init --model`.
- **No in-tool LLM or cross-encoder reranker**: With blind top-1 retrieval accuracy reaching 0.90–0.95, a neural reranker was unnecessary. Page summarization and extraction are handled by the calling host agent already in context, keeping `mf` deterministic, local, and sub-second.
- **In-flight session capture over post-hoc transcript parsing**: Parsing 50–200K token transcripts at session end without an LLM exceeded hook budgets. Instead, `mf hook stop` prompts the agent to capture findings while context is active, and `mf hook session-end` only stages a minimal metadata pointer (<0.25s execution).

## Using it with an agent

A Claude Code skill that teaches the lean calls, the confidence
contract, and the write path ships in
[.claude/skills/mf](.claude/skills/mf). Copy it into your project's
`.claude/skills/` to use mf there.

Two hooks close the loop at session end. `mf hook stop` asks the agent
to capture what it learned before it finishes, once per session. `mf
hook session-end` writes a transcript pointer into the field's `raw/`
staging area, ready for `mf consolidate --plan`.

The settings snippet is in
[.claude/skills/mf/reference.md](.claude/skills/mf/reference.md). Use
the installed `mf` binary in the hook command: SessionEnd hooks get
about 1.5 seconds in total.

## Commands

Full arguments, flags, exit codes, and JSON outputs are documented in [docs/CLI.md](docs/CLI.md).

| Command | What it does |
|---|---|
| `mf init [DIR]` | create `mf.sqlite3` in a field, pinning model and dimension |
| `mf index [DIR]` | scan the field's pages into the index |
| `mf search "<query>"` | stub-first lookup with the confidence gate |
| `mf read <uuid>[#section] ...` | read the answer section, one section, or L2 |
| `mf write <draft>` | validate, dedup-check, copy in, and index a draft |
| `mf raw add` | stage a freeform session extract under `raw/` |
| `mf lint [DIR]` | check writing conventions and index drift, `--check` for CI |
| `mf pack` / `mf unpack` | reproducible archive plus sha256 sidecar, verified extraction |
| `mf import claude-memory <dir>` | turn a Claude Code memory directory into pages |
| `mf import wiki <dir>` | turn an index.md-style wiki into pages |
| `mf hook stop` / `mf hook session-end` | Claude Code hook handlers |
| `mf model list` | list available embedding models, dimensions, speeds, and cache status |
| `mf model install <name>` | download and cache an embedding model ahead of time |
| `mf claim <slug> --by <writer>` | atomically claim a slug before creating a page (multi-writer) |
| `mf consolidate --plan` | propose create/review actions from `raw/` entries |

## Importing existing notes

`mf import claude-memory <dir>` turns a Claude Code auto-memory
directory (`MEMORY.md` plus topic files) into pages under
`<field>/claude-memory/`. `mf import wiki <dir>` does the same for an
index.md-style wiki with pages in subdirectories, flattened into
`<field>/wiki/`.

Both are un-gated bulk imports: the dedup gate does not run. uuids
derive from the source names, so a re-import updates in place, and
`source` points back at the original file. `--dry-run` lists the plan
before anything is written. Run `mf lint` after importing.

## Keeping a field healthy

Retrieval quality holds only while pages follow the writing
conventions, so `lint` is part of the tool rather than a linter you
might add later. `mf lint --check` exits 1 on any error or warning.
`mf search` refuses a stale index (exit 3) until `mf index` runs, so
refresh the index after commits.

Git hooks (drop into `.git/hooks/`, `chmod +x`):

```bash
#!/bin/sh
# .git/hooks/pre-commit
mf lint --check . || exit 1
```

```bash
#!/bin/sh
# .git/hooks/post-commit
mf index . >/dev/null
```

<details>
<summary>GitHub Actions job (the index is derived, so CI only lints)</summary>

```yaml
lint-field:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v5
    - run: uv tool install git+https://github.com/<you>/mf
    - run: mf lint --check .
```

</details>

## Eval harness

Every retrieval decision in mf was measured, not assumed. The repo
ships a 157-page labeled corpus, a 458-query set plus blind
vocabulary-mismatch sets, and six baselines (grep, FTS5, TF-IDF,
nomic, BGE-large, and hybrid).

The query set shares an authoring process with the corpus, so scores
sit near ceiling. Read the numbers with that in mind, in
[docs/M0.5_REPORT.md](docs/M0.5_REPORT.md).

```bash
uv sync --extra eval              # fastembed into a local venv
uv sync --extra eval --extra mlx  # optional, Apple Silicon MLX variants
uv run python3 -m eval.run_baselines   # 45+ minutes wall time
uv run python3 -m eval.report          # render the report
```

## Development

```bash
uv sync --extra eval --group dev
uv run pytest tests/
```

`uv sync` calls do not compose: each one resets the venv to exactly
what that call specifies. Pass `--extra eval` and `--group dev`
together, in one invocation.

## Status

Read path, write path, and hooks/imports are built and tested. In
progress: multi-writer support (`mf claim`, `mf consolidate --plan`).
The per-item record of what was built, measured, and changed is in
[ROADMAP.md](ROADMAP.md). CLAUDE.md is the map for anyone working in
the repo.

## License

MIT. See [LICENSE](LICENSE).
