# mf

Search-first memory for coding agents: plain Markdown pages, SQLite
search, and no LLM in the loop.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

[Install](#install) · [Quickstart](#quickstart) · [Design decisions](#design-decisions) · [Agents](#using-it-with-an-agent) · [Documentation](#documentation)

A field is a directory of Markdown pages with frontmatter. mf indexes
it into SQLite and answers a question with stubs, not pages: the agent
reads a one-line summary first and opens the body only when it needs
to.

The page format is Cal Paterson's
[memoryfield](https://calpaterson.com/memoryfields.html) spec
([vendored copy](docs/upstream/SPEC.md)). Any spec field loads
unchanged, `mf pack --spec` writes one back out, and everything mf adds
on top is its own measured design.

Session-injected memory costs the same on every task, whether or not it
gets used. mf moves that cost to lookup time: about 100 tokens for a
default search and 55 for a point lookup, measured over 20 real agent
tasks ([Benchmarks, section 4](docs/BENCHMARKS.md#4-token-cost-benchmarks)).
Most lookups end at the stub.

## Why mf

- **Stubs, not pages.** A search returns uuid, title, and a summary
  written as the answer. Reads tier up only when the stub is not
  enough.
- **A confidence line you can act on.** `high`, `low`, or `none` before
  every result, from a gate calibrated on blind phrasing to demote
  rather than overclaim.
- **A write path with a dedup gate.** `mf write` validates, checks for
  near-duplicates, copies in, and indexes in one step.
- **Plain files, spec-compatible.** Pages stay Markdown you can read,
  diff, and edit, and any memoryfield reader can load them.
- **Measured, not assumed.** Every ranking, gate, and default was run
  through the real pipeline on queries written without seeing the
  corpus before it was hardcoded.

## Install

Python 3.11 or newer, installed through [uv](https://docs.astral.sh/uv/):

```bash
uv tool install .                        # from a checkout
uv tool install git+https://github.com/whit3rabbit/memoryfield
```

The first search downloads the embedding model (default
`snowflake-arctic-embed-xs`, 384-d, about 170 MB). The model is pinned
per field at `mf init`. Alternatives, and when to pick one:
[docs/models.md](docs/models.md).

`mf mcp` (an MCP server for `search`/`read`/`write`/`raw_add`) needs an
extra: `uv tool install ".[mcp]"`. It's optional because most usage is
the CLI directly or the Claude Code skill, and the MCP stack (roughly
a dozen extra packages) isn't worth pulling in for those.

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

When the stub is not enough, `mf read <uuid>` returns the page's answer
section, and `--tier L2` or `<uuid>#section` returns more.

New pages go
in through `mf write <draft> --field <dir>`, drafted outside the field.
Exit 2 means a near-duplicate was flagged. The calling contract an
agent should follow is in [docs/agents.md](docs/agents.md), and every
flag is in [docs/CLI.md](docs/CLI.md#mf-write).

## Design decisions

Each choice below was measured on a 157-page corpus, blind phrasing
sets, and one field this project did not write. The numbers live
behind the links, not here, so they cannot drift.

- **Dense-first ranking.** The vector index ranks. FTS runs on every
  query as a gate signal and a fallback, never as the primary ranker,
  because fusing the two averaged keyword noise into good semantic
  rankings. [Benchmarks, section 2](docs/BENCHMARKS.md#2-ranking-architecture-benchmarks)
- **A three-signal confidence gate.** A BM25 floor alone demoted nearly
  half of the answerable blind queries and collapsed on small fields.
  The gate now combines a dense distance floor, the BM25 score, and
  top-1 agreement. [Benchmarks, section 3](docs/BENCHMARKS.md#3-confidence-gate-benchmarks)
- **Lean stubs by default.** Two stubs and no neighbors, because the
  original five stubs and three neighbors cost more tokens than
  exploring raw files did. [Benchmarks, section 4](docs/BENCHMARKS.md#4-token-cost-benchmarks)
- **A write-time dedup gate.** Cosine distance on title, summary, and
  first section, with the threshold set on a labeled paraphrase set.
  It catches copies and light rewordings, not thorough rewrites.
  [Architecture, section 5](docs/architecture.md#5-write)
- **A small default embedder, pinned per field.** A 384-d model that
  matched the larger ones on blind accuracy at a fraction of the load
  time and storage. [docs/models.md](docs/models.md)
- **No LLM and no reranker inside the tool.** The host agent already in
  context does extraction and judgment. mf stays deterministic, local,
  and sub-second. [Architecture, "Stack"](docs/architecture.md#stack)

## Using it with an agent

A Claude Code skill that teaches the lean calls, the confidence
contract, and the write path ships in
[.claude/skills/mf](.claude/skills/mf). Copy it into your project's
`.claude/skills/` to use mf there.

Two hooks, `mf hook stop` and `mf hook session-end`, ask the agent to
capture what it learned before it finishes and stage a transcript
pointer for later consolidation. Setup, the hooks snippet, and the
calling contract: [docs/agents.md](docs/agents.md).

## Commands

Full arguments, flags, exit codes, and JSON outputs are documented in
[docs/CLI.md](docs/CLI.md).

| Command | What it does |
|---|---|
| `mf init [DIR]` | create `mf.sqlite3` in a field, pinning model and dimension |
| `mf index [DIR]` | scan the field's pages into the index |
| `mf search "<query>"` | stub-first lookup with the confidence gate |
| `mf read <uuid>[#section] ...` | read the answer section, one section, or L2 |
| `mf write <draft>` | validate, dedup-check, copy in, and index a draft |
| `mf raw add` | stage a freeform session extract under `raw/` |
| `mf lint [DIR]` | check writing conventions and index drift, `--check` for CI |
| `mf pack` / `mf unpack` | reproducible archive plus sha256 sidecar, verified extraction, `--spec` for other memoryfield readers |
| `mf import claude-memory <dir>` | turn a Claude Code memory directory into pages |
| `mf import wiki <dir>` | turn an index.md-style wiki into pages |
| `mf hook stop` / `mf hook session-end` | Claude Code hook handlers |
| `mf model list` | list available embedding models, dimensions, speeds, and cache status |
| `mf model install <name>` | download and cache an embedding model ahead of time |
| `mf claim <slug> --by <writer>` | atomically claim a slug before creating a page (multi-writer) |
| `mf consolidate --plan` | propose create/review actions from `raw/` entries |
| `mf mcp` | run an MCP server exposing `search`/`read`/`write`/`raw_add` over stdio |

## Documentation

| Guide | What you can do |
|---|---|
| [Agents](docs/agents.md) | Wire mf into Claude Code: the skill, the hooks, and the lean-call contract. |
| [CLI reference](docs/CLI.md) | Look up every flag, exit code, and JSON shape. |
| [Models](docs/models.md) | Pick, pin, and pre-download an embedding model. |
| [Fields](docs/fields.md) | Write pages, lint, wire git hooks, import notes, and exchange fields with other memoryfield tools. |
| [Architecture](docs/architecture.md) | See the schema, how a search is ranked and gated, and the record of each decision. |
| [Benchmarks](docs/BENCHMARKS.md) | Read the numbers behind the design decisions. |
| [Docs index](docs/README.md) | Start from a task and find the right guide. |

## Eval harness

The repo ships a 157-page labeled corpus, a 458-query set plus blind
vocabulary-mismatch sets, and six baselines (grep, FTS5, TF-IDF, nomic,
BGE-large, and hybrid).

The in-vocabulary scores sit near ceiling
because the queries share an authoring process with the corpus. Read
[docs/M0.5_REPORT.md](docs/M0.5_REPORT.md) with that in mind, and
[docs/BENCHMARKS.md](docs/BENCHMARKS.md) section 5 for the soapstones
field, the first corpus outside that process.

```bash
uv sync                            # fastembed is a core dependency
uv sync --extra mlx                # optional, Apple Silicon MLX variants
uv run python3 -m eval.run_baselines   # 45+ minutes wall time
uv run python3 -m eval.report          # render the report
uv run python3 eval/fetch_soapstones.py                        # pinned foreign-field fixture
uv run python3 -m eval.calibrate_confidence_blind soapstones   # ranking and gate on it
```

## Development

```bash
uv sync --group dev
uv run pytest tests/
```

`uv sync` calls do not compose: each one resets the venv to exactly
what that call specifies. Pass every extra and group you need in
one invocation.

## Status

Read path, write path, and hooks/imports are built and tested. In
progress: multi-writer support (`mf claim`, `mf consolidate --plan`).
The per-item record of what was built, measured, and changed is in
[ROADMAP.md](ROADMAP.md). CLAUDE.md is the map for anyone working in
the repo.

## License

MIT. See [LICENSE](LICENSE).
