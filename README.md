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

Python 3.11 or newer. The package on PyPI is `memoryfield`, the
command it installs is `mf`. Pick one:

```bash
uv tool install memoryfield              # uv (https://docs.astral.sh/uv/)
pipx install memoryfield                 # pipx
```

For the unreleased tip of `main`:

```bash
uv tool install git+https://github.com/whit3rabbit/memoryfield
```

The first search downloads the embedding model (default
`snowflake-arctic-embed-xs`, 384-d, about 170 MB). The model is pinned
per field at `mf init`. Alternatives, and when to pick one:
[docs/models.md](docs/models.md).

That install includes `mf mcp`, an MCP server for
`search`/`read`/`write`/`raw_add`, so the MCP entry the setup wizard
writes works without a second install step.

Working on mf itself? Install from your checkout instead. See
[Development](#development).

## Quickstart

This walks through adding mf to a project you already have, with a
coding agent writing the first pages from the code. The example
project is this repo, and the field it builds is the real one at
[notes/](notes/). The output is real, with paths shortened.

### 1. Create the field and wire your agent

From the project root:

```console
$ mf init
Initialized empty field at /path/to/myapp/notes/mf.sqlite3 (model snowflake-arctic-embed-xs, 384-d)
```

The field defaults to `notes/`, a subdirectory, so the project's own
Markdown never becomes memory by accident. Pass a directory to put it
elsewhere. Every other command looks at the cwd first and falls back
to `./notes`, so `mf search` from the project root finds it without a
flag.

On a terminal, `mf init` keeps going. It asks which coding agents use
the project (Claude Code, Codex, Cursor, Copilot, OpenCode, Gemini
CLI, Antigravity, Windsurf, Amp, Pi, with the ones it detects
pre-checked), then what to install, then shows the plan and asks
before writing anything:

```console
Would install for field notes under /path/to/myapp
  create    CLAUDE.md  (instructions: claude)
  create    .claude/skills/mf/SKILL.md  (skill: claude)
  create    .claude/skills/mf/reference.md  (skill: claude)
  create    .mcp.json  (mcp: claude)
  create    .claude/settings.json  (hooks: claude)
  create    AGENTS.md  (instructions: codex)
  create    .agents/skills/mf/SKILL.md  (skill: codex)
  create    .agents/skills/mf/reference.md  (skill: codex)
  create    .codex/config.toml  (mcp: codex)
  create    notes/.gitignore  (gitignore: field)
```

The instruction lines land in a fenced block, the skill is the same
one this repo uses, the MCP entry runs the server that ships with the
package, the hooks carry `--field notes`, and the field's `.gitignore`
keeps the index out of git. Rerunning is a no-op.
`mf setup` reruns the wizard later, and `mf setup install`,
`uninstall`, and `status` do the same from a script. Pass
`--no-setup` to get the old one-line `init`.

The model is pinned per field at `init`, so read
[docs/models.md](docs/models.md) first if the default is not what you
want. Every harness path and flag: [docs/CLI.md](docs/CLI.md#mf-setup).

### 2. Have the agent seed the field

The wizard ends by printing this prompt, and `mf setup prompt` prints
it again. Paste it into Claude Code, Codex, OpenCode, or whatever you
run, from the project root:

```
Read .claude/skills/mf/reference.md, then explore this repo and seed the
memoryfield in notes/. Write one page per question a new contributor
would ask on day one: how to run the tests, how to run it locally, how a
release or deploy happens, where config lives, and every gotcha you find
in comments, CI config, or recent commits. Draft each page outside
notes/ and add it with `mf write <draft> --field notes`. If write exits
2, update the page it names instead of forcing. Run `mf lint --field
notes` when you are done and fix what it reports.
```

Each page the agent produces looks like this. The summary is the
answer, not the topic, because the summary is what `search` returns:

```markdown
---
uuid: cut-release
title: "Release: how a version reaches PyPI"
summary: "Push to main, then `git tag vX.Y.Z && git push origin vX.Y.Z`. release.yml publishes via trusted-publisher OIDC; the version lives only in mf/__init__.py."
status: active
tags: [release, ci]
source: CLAUDE.md
---
## Answer
Bump `__version__` in `mf/__init__.py`, push to `main`, then tag ...

## Don't
Don't expect a test gate before publish. ...
```

```console
$ mf write /tmp/cut-release.md --field notes
Wrote cut-release to cut-release.md
```

`write` validates, checks for a near-duplicate, copies the draft in,
and indexes it. When the agent tries to add a page that already
exists under a different name, the gate stops it:

```console
$ mf write /tmp/running-tests.md --field notes
mf write: 1 possible near-duplicate(s) found; not written.
  - [run-tests] Tests: how to run the suite (distance 0.012)
      `uv run pytest tests/ -q` from the repo root. Tests are hermetic (no model download) except tests/test_token_regression.py.
Use --update <uuid> to update an existing page, or --force to write anyway.
```

Exit 2. The agent updates the existing page with `--update run-tests`
or moves on. Nothing un-gated lands in the field.

Already have notes? `mf import claude-memory <dir>` turns a Claude
Code auto-memory directory into pages, and `mf import wiki <dir>`
does the same for an index.md wiki. Both skip the gate, so run `mf
lint` after. [docs/fields.md](docs/fields.md#importing-existing-notes).

### 3. Search it

Three pages in, the agent's next session starts with a lookup instead
of a cold read of the tree:

```console
$ mf search "why does the mac CI job use brew python" --field notes
confidence: high
- [ci-macos-python] CI: why the macOS leg installs Python from Homebrew
    sqlite-vec needs a Python built with --enable-loadable-sqlite-extensions. uv-managed and actions/setup-python builds on the macOS runner lack it, so test.yml uses Homebrew Python with UV_PYTHON_PREFERENCE=only-system.
- [cut-release] Release: how a version reaches PyPI
    Push to main, then `git tag vX.Y.Z && git push origin vX.Y.Z`. release.yml publishes via trusted-publisher OIDC; the version lives only in mf/__init__.py.
```

Read the confidence line before the results:

- `high`: the stub is safe to cite.
- `low`: a strong lead. `mf read <uuid>` for the page's answer section
  before quoting it.
- `none`: do not cite it.

The gate errs toward demotion. On a field this small, expect `low`
often, even when the top stub is right:

```console
$ mf search "how do I run the tests" --field notes
confidence: low
- [run-tests] Tests: how to run the suite
    `uv run pytest tests/ -q` from the repo root. Tests are hermetic (no model download) except tests/test_token_regression.py.
- [ci-macos-python] CI: why the macOS leg installs Python from Homebrew
    sqlite-vec needs a Python built with --enable-loadable-sqlite-extensions. uv-managed and actions/setup-python builds on the macOS runner lack it, so test.yml uses Homebrew Python with UV_PYTHON_PREFERENCE=only-system.
```

When the stub is not enough, `mf read <uuid>` returns the page's
answer section, and `--tier L2` or `<uuid>#section` returns more.

### 4. Keep it alive

The field pays off only if pages keep landing. Three things do that:

- The instruction lines from step 1, so every session searches first
  and writes last.
- `mf lint --check notes` in a pre-commit hook and `mf index notes`
  in post-commit. `search` refuses a stale index (exit 3) until
  `index` runs. Snippets: [docs/fields.md](docs/fields.md#keeping-a-field-healthy).
- For Claude Code, the `mf hook stop` and `mf hook session-end`
  hooks the wizard wrote, which remind the agent to capture what it
  learned and stage a transcript pointer for `mf consolidate --plan`.
  [docs/agents.md](docs/agents.md#hooks).

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

`mf init` on a terminal, or `mf setup` any time after, installs what
each harness needs: the instruction lines, the skill that teaches the
lean calls and the confidence contract
([.claude/skills/mf](.claude/skills/mf) is this repo's own copy), an
`mf mcp` entry, and for Claude Code the two hooks, `mf hook stop` and
`mf hook session-end`, that ask the agent to capture what it learned
before it finishes and stage a transcript pointer for later
consolidation. Ten harnesses in this cut. Where each keeps its files
comes from [agent-config](https://github.com/whit3rabbit/agent-config).
The calling contract: [docs/agents.md](docs/agents.md).

## Commands

Full arguments, flags, exit codes, and JSON outputs are documented in
[docs/CLI.md](docs/CLI.md).

| Command | What it does |
|---|---|
| `mf init [DIR]` | create `mf.sqlite3` in a field (default `notes/`), pinning model and dimension, then wire a coding agent on a terminal |
| `mf setup` | install, uninstall, or inspect a harness's instructions, skill, MCP entry, and hooks |
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

From a checkout of this repo:

```bash
uv sync --group dev
uv run pytest tests/
uv tool install --force .                # the global `mf` from this checkout
```

`uv run mf ...` picks up source changes immediately. The global tool
does not, so rerun `uv tool install --force .` after editing.

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
