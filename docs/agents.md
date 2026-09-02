# Using mf with an agent

[Docs](README.md) | [Agents](agents.md) | [CLI](CLI.md) | [Models](models.md) | [Fields](fields.md) | [Architecture](architecture.md) | [Benchmarks](BENCHMARKS.md)

mf is built to be called by a coding agent mid-task. A lookup costs
about 100 tokens, the answer is in the stub most of the time, and the
confidence line tells the agent whether to cite it. This guide covers
the Claude Code skill, the two hooks, and the calling contract the
skill teaches. The numbers behind each rule are in the skill's own
[reference.md](../.claude/skills/mf/reference.md).

## What the agent gets

A search returns stubs, not pages: uuid, title, and a one-line summary
written to be the answer. The agent reads the summary and opens the
body only when it needs to.

Session-injected memory costs the same on every task, whether or not
it gets used. mf moves that cost to lookup time, measured at about 100
tokens for a default search and 55 for a point lookup ([Benchmarks,
section 4](BENCHMARKS.md#4-token-cost-benchmarks)).

## Install the skill

A Claude Code skill that teaches the lean calls, the confidence
contract, and the write path ships in
[.claude/skills/mf](../.claude/skills/mf). Copy the directory into
your project's `.claude/skills/` to use mf there. The skill triggers
whenever the working directory has an `mf.sqlite3`, or when the user
asks for a memoryfield page.

Two lines in the project's CLAUDE.md or AGENTS.md are enough on top of
that:

```
Before exploring this codebase, run `mf search "<question>" --field .`.
Before finishing, write what you learned as a page with `mf write`, or stage it with `mf raw add`.
```

## The lean-call contract

The defaults are a measured cost decision, not a convenience
([ROADMAP.md](../ROADMAP.md) 2.11). The skill teaches this shape:

- `mf search "<question>" --field <dir>` with no other flags: two
  stubs, no neighbors.
- `--limit 1` for a point lookup the agent is sure of.
- Widen with `--limit 3` or `--neighbor-limit 1` only when confidence
  is `low` or `none`, or the question is genuinely broad. Each
  neighbor slot roughly doubles the call.
- `mf read <uuid>` returns L1, the answer section. `--tier L2` or
  `<uuid>#section` only when L1 is not enough.
- Batch the reads for one task into a single `mf read a b` call. That
  is what records `co_read`, the signal neighbor ranking uses.

Token cost per call shape: [reference.md, "Why the lean
call"](../.claude/skills/mf/reference.md#why-the-lean-call).

## Reading confidence

Read the confidence line before the results.

- `high`: the stub is safe to cite.
- `low`: a strong lead. Read the page's answer section with `mf read`
  before quoting it.
- `none`: do not cite it. What comes back is a best-effort guess.

The gate errs toward demotion, not overclaiming. Three signals feed
it: a lexical floor on the FTS top score, a cosine floor on the
embedding top hit, and whether the two retrievers agree on the top
page. Measured false-high and usable-answer rates are in [Benchmarks,
section 3](BENCHMARKS.md#3-confidence-gate-benchmarks) and
[reference.md](../.claude/skills/mf/reference.md#what-confidence-means).

## Writing back

New pages go in through `mf write <draft> --field <dir>`, with the
draft written outside the field. It validates, dedup-checks, copies
the page in, and indexes it in one step.

Exit 2 means a near-duplicate was flagged: update that page with
`--update <uuid>`, or `--force` if the page really is new. Retire a
page by writing its replacement with `supersedes: [old-uuid]`, never
by deleting the file. Page conventions, and why the draft stays
outside the field: [Fields](fields.md#writing-pages).

## Hooks

Two Claude Code hooks close the loop at session end. Both are handled
by `mf` itself, reading the hook JSON on stdin.

- `mf hook stop` runs when the agent is about to finish a turn. Once
  per session, if the directory is a field and nothing has been
  written yet, it adds one reminder: write the reusable lesson as a
  page, pipe a short extract to `mf raw add`, or just finish. It stays
  silent on every later turn of that session.
- `mf hook session-end` writes a pointer entry into the field's `raw/`
  staging area (session id, transcript path, end reason), never the
  transcript body. `mf consolidate --plan` reads those entries later.

Add this to `.claude/settings.json` (or `settings.local.json`) in a
project whose root is a field. It is the same snippet as the skill's
reference.md, kept in both places so the skill stays self-contained
when copied into another repo:

```json
{
  "hooks": {
    "Stop": [{"hooks": [{"type": "command", "command": "mf hook stop"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "mf hook session-end"}]}]
  }
}
```

Use the installed `mf` binary in the hook command, not `uv run`.
SessionEnd hooks share a 1.5-second budget, and the installed binary
handles the pointer write in about a quarter of a second.

Why capture happens while the agent's context is still hot, rather
than by parsing the transcript afterwards: [Architecture, section
7](architecture.md#7-session-capture).

## A worked example

This repo's own `notes/` directory is a real field: an `mf.sqlite3`
at its root, the two hooks wired in `notes/.claude/settings.json`, its
own CLAUDE.md, and real `raw/` entries. The repo root is deliberately
not a field, because a root-level index would sweep the eval corpus in
as memory. [Architecture, section 7](architecture.md#7-session-capture)
has the detail.

## Other agents

Every command takes `--json` and returns the shapes documented in the
[CLI reference](CLI.md), so any agent that can run a subprocess can use
mf today. An MCP server wrapping search, read, write, and raw add is
[ROADMAP.md](../ROADMAP.md) 5.1 and is not built yet.
