# MF — Memoryfields

Start here:

- **[CLAUDE.md](CLAUDE.md)** — context for the next agent (human or model). Gotchas, lessons learned, current state, roadmap status. Read this first.
- **[PLAN.md](PLAN.md)** — the design document. Architecture, writing conventions, stack, milestones.

- **[docs/architecture.md](docs/architecture.md)** — what the schema and retrieval design currently are, with the measurements behind each decision.
- **[ROADMAP.md](ROADMAP.md)** — phase status and the per-item record of what was built, measured, and changed.

## Repo status

- **Eval harness complete (M0/M0.5).** 157-page labeled corpus, 458-query
  set plus blind vocabulary-mismatch sets, six baselines. Results in
  `eval/results/`, reports in `M0.5_REPORT.md`.
- **Every Phase 1 and 2 command is real** (`init`, `index`, `search`,
  `read`, `write`, `lint`, `pack`/`unpack`, `raw add`) and verified
  against the full corpus. Next: Phase 3, hooks and imports. Retrieval is dense-first with a
  three-signal confidence gate, both calibrated on blind queries through
  the real pipeline (ROADMAP.md 2.6-2.7).
- **Index schema is v2** (cosine `vec`). A v1 `mf.sqlite3` is refused:
  delete it, `mf init`, `mf index`.

## Session-end capture

`mf hook stop` and `mf hook session-end` are Claude Code hook handlers
(ROADMAP.md 3.1). The settings snippet and the two-line CLAUDE.md text
are in [.claude/skills/mf/reference.md](.claude/skills/mf/reference.md).
Use the installed `mf` binary in the hook command: SessionEnd hooks get
1.5 seconds in total.

## Quick start

```bash
# Install the mf CLI
uv tool install .
mf init /path/to/field && mf index /path/to/field   # --model bge-large-en-v1.5 for a 1024-d field
mf search "how do we roll back a deploy" --field /path/to/field

# Install eval's dependencies (fastembed) into a local venv
uv sync --extra eval

# Optional, Apple Silicon only: adds MLX (Metal GPU) versions of the
# nomic/bge dense baselines alongside the fastembed ones. Falls back
# to fastembed automatically on any other platform.
uv sync --extra eval --extra mlx

# Run all baselines on the current query set (45+ minutes wall time)
uv run python3 -m eval.run_baselines

# Per-axis breakdown
uv run python3 -m eval.axis_breakdown

# Render reports
uv run python3 -m eval.report
```

Results land in `eval/results/*.json`. Reports in `M0_REPORT.md` and
`M0.5_REPORT.md` at the repo root.

## Tests

`mf/`'s unit tests (`tests/`) need only the `dev` group; some import
code that also needs the `eval` extra (fastembed), so sync both:

```bash
uv sync --extra eval --group dev
uv run pytest tests/
```

`uv sync --extra eval` and `uv sync --group dev` don't compose across
separate invocations — each `uv sync` call resets the venv to exactly
what that invocation specifies, so pass both flags together.
