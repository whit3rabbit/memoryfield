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

## Install with `mf setup`

`mf init` from the project root creates the field at `notes/` and, on
a terminal, walks through the rest: which coding agents use the project,
and whether to install the instruction lines, the skill, an MCP
entry, and (Claude Code) the hooks. `mf setup` reruns the wizard.
`mf setup install`, `uninstall`, and `status` do the same without
prompts. Every flag: [CLI reference](CLI.md#mf-setup).

```bash
mf setup install --harness claude --all-surfaces --field notes
mf setup status
```

Ten harnesses are wired in this cut, in the wizard's menu order:
Claude Code, Codex CLI, Cursor, GitHub Copilot, OpenCode, Gemini CLI,
Google Antigravity, Windsurf, Amp, and Pi. Where each one keeps its
files comes from [agent-config](https://github.com/whit3rabbit/agent-config),
and the markers mf writes are that crate's, so the two tools can
manage the same files. Hooks are Claude Code only for now: `mf hook`
parses Claude Code's payload, and no other harness's hook payload has
been verified.

The skill itself teaches the lean calls, the confidence contract, and
the write path. It ships inside the package (`mf/templates/skill/`),
and the copy at [.claude/skills/mf](../.claude/skills/mf) is this
repo's own install of it. Copying that directory into a project's
`.claude/skills/` by hand still works. The skill triggers whenever
the working directory has an `mf.sqlite3`, or when the user asks for a
memoryfield page.

The instruction surface is two lines in the project's CLAUDE.md or
AGENTS.md, inside a fenced block so `uninstall` can find them again:

```
Before exploring this codebase, run `mf search "<question>" --field notes`.
Before finishing, write what you learned as a page with `mf write <draft> --field notes`, or stage it with `mf raw add --field notes`.
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

`mf setup install --harness claude --hooks` writes them. By hand, add
this to `.claude/settings.json` (or `settings.local.json`) at the
project root. It is the same snippet as the skill's reference.md, kept
in both places so the skill stays self-contained when copied into
another repo:

```json
{
  "hooks": {
    "Stop": [{"hooks": [{"type": "command", "command": "mf hook stop --field notes"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "mf hook session-end --field notes"}]}]
  }
}
```

Claude Code runs hooks with cwd set to the project root, not to the
field. `--field notes` joins the field onto that cwd. Without it, the
hooks fire only in a project whose root is the field, and stay silent
everywhere else.

Use the installed `mf` binary in the hook command, not `uv run`.
SessionEnd hooks share a 1.5-second budget, and the installed binary
handles the pointer write in about a quarter of a second.

Why capture happens while the agent's context is still hot, rather
than by parsing the transcript afterwards: [Architecture, section
7](architecture.md#7-session-capture).

## A worked example

This repo's own `notes/` directory is a real field: an `mf.sqlite3`
at its root, the two hooks wired in `notes/.claude/settings.json` (a
session started inside `notes/`), its own CLAUDE.md, and real `raw/`
entries. The repo root is deliberately
not a field, because a root-level index would sweep the eval corpus in
as memory. [Architecture, section 7](architecture.md#7-session-capture)
has the detail.

## Other agents

Every command takes `--json` and returns the shapes documented in the
[CLI reference](CLI.md), so any agent that can run a subprocess can use
mf today. `mf mcp` runs an MCP server (stdio) wrapping search, read,
write, and raw add with the same JSON contract. `mf setup install
--mcp` writes the entry. See the [CLI reference](CLI.md#mf-mcp).
