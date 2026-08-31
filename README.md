# MF — Memoryfields eval harness

Start here:

- **[CLAUDE.md](CLAUDE.md)** — context for the next agent (human or model). Gotchas, lessons learned, current state, roadmap status. Read this first.
- **[PLAN.md](PLAN.md)** — the design document. Architecture, writing conventions, stack, milestones.

## Repo status

- **M0 + M0.5 eval harness complete.** 157-page labeled corpus, 458-query
  set (lexical + blind paraphrases + no-answer queries), six baselines
  (grep, FTS5, TF-IDF, nomic, BGE-large, hybrid).
- **No tool implementation yet.** `mf init` / `mf index` / `mf search` /
  `mf read` / `mf write` land in M1.

## Quick start

```bash
# Run all baselines on the current query set (45+ minutes wall time)
~/.hermes/hermes-agent/venv/bin/python3 -m harness.run_baselines

# Per-axis breakdown
~/.hermes/hermes-agent/venv/bin/python3 -m harness.axis_breakdown

# Render reports
~/.hermes/hermes-agent/venv/bin/python3 -m harness.report
```

Results land in `harness/results/*.json`. Reports in `M0_REPORT.md` and
`M0.5_REPORT.md` at the repo root.
