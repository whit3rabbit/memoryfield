# MF — Memoryfields

Start here:

- **[CLAUDE.md](CLAUDE.md)** — context for the next agent (human or model). Gotchas, lessons learned, current state, roadmap status. Read this first.
- **[PLAN.md](PLAN.md)** — the design document. Architecture, writing conventions, stack, milestones.

## Repo status

- **M0 + M0.5 eval harness complete.** 157-page labeled corpus, 458-query
  set (lexical + blind paraphrases + no-answer queries), six baselines
  (grep, FTS5, TF-IDF, nomic, BGE-large, hybrid).
- **`mf` CLI is a stub.** `mf init` / `mf index` / `mf search` / `mf read` /
  `mf write` all exist as subcommands but aren't implemented yet — that
  lands starting M1 (ROADMAP.md Phase 1).

## Quick start

```bash
# Install the mf CLI (stub commands only until M1 lands)
uv tool install .
mf --help

# Install eval's dependencies (fastembed) into a local venv
uv sync --extra eval

# Run all baselines on the current query set (45+ minutes wall time)
uv run python3 -m eval.run_baselines

# Per-axis breakdown
uv run python3 -m eval.axis_breakdown

# Render reports
uv run python3 -m eval.report
```

Results land in `eval/results/*.json`. Reports in `M0_REPORT.md` and
`M0.5_REPORT.md` at the repo root.
