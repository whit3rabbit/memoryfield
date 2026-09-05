# mf documentation

[Docs](README.md) | [Agents](agents.md) | [CLI](CLI.md) | [Models](models.md) | [Fields](fields.md) | [Architecture](architecture.md) | [Benchmarks](BENCHMARKS.md)

The [project README](../README.md) gets you from install to a first
search. These guides cover the rest: wiring mf into an agent, every
flag, choosing a model, keeping a field healthy, and the schema and
evidence behind each retrieval decision.

## Start here

| I want to... | Read |
|---|---|
| Add mf to a project and have an agent seed the field | [Quickstart](../README.md#quickstart) in the project README |
| Use mf from Claude Code | [Agents](agents.md) |
| Look up a flag, exit code, or JSON shape | [CLI reference](CLI.md) |
| Pick or change the embedding model | [Models](models.md) |
| Write pages, lint, wire git hooks, import notes, exchange fields with other tools | [Fields](fields.md) |
| Understand how a search is ranked and gated | [Architecture, section 3](architecture.md#3-retrieval) |
| See the numbers behind a design decision | [Benchmarks](BENCHMARKS.md) |
| Read the raw eval report | [M0.5 report](M0.5_REPORT.md) |
| Read the page format spec | [upstream/SPEC.md](upstream/SPEC.md) |
| See what was decided, when, and on what evidence | [ROADMAP.md](../ROADMAP.md) |
| Work on mf itself | [CLAUDE.md](../CLAUDE.md) |

## Recommended paths

**Using mf through an agent.** Quickstart, then [Agents](agents.md)
for the skill, the hooks, and the lean-call contract. The [CLI
reference](CLI.md) has `mf search`, `mf read`, and `mf write` in full.
[Fields](fields.md) covers what happens after the first hundred pages.

**Using mf from a terminal.** Quickstart, then the [CLI
reference](CLI.md). Read [Models](models.md) before the first `mf init`
on a field that matters, since the model is pinned per field.
[Fields](fields.md) for lint, hooks, and imports.
[Architecture](architecture.md) when you want to know why a search
returned what it did.

**Working on mf or its eval harness.** [CLAUDE.md](../CLAUDE.md)
first. It is the contributor map and the gotcha list. Then
[Architecture](architecture.md), [Benchmarks](BENCHMARKS.md), the
[M0.5 report](M0.5_REPORT.md), and [eval/README.md](../eval/README.md).

## Reading the numbers

Every retrieval decision in mf was measured before it was hardcoded,
and the measurements have a known limit. The 157-page corpus and its
458 queries share one authoring process, so in-vocabulary scores sit
near ceiling. The blind phrasing sets and the soapstones field (95
pages this project did not write) are the numbers to trust for a
corpus with a different author. [Benchmarks](BENCHMARKS.md) reports
both, and CLAUDE.md gotcha 7 is the full caveat.

## Generated and vendored files

Three files in this directory are not hand-edited:

- `M0.5_REPORT.md` is written by `eval/report.py` from
  `eval/results/summary.json`. Regenerate it with `uv run python3 -m
  eval.report`. Edits made by hand are lost on the next run.
- `M0_REPORT.md` is the frozen M0 snapshot. No script regenerates it,
  and its header still names the `harness/` directory that became
  `eval/`. It stays as the record.
- `upstream/SPEC.md` is Cal Paterson's memoryfield spec, vendored
  verbatim.
- `upstream/agent-config-agents.json` is the harness path schema from
  whit3rabbit/agent-config, vendored verbatim. `upstream/agent-config-agents.md`
  records the version and date, and `tests/test_harnesses.py` checks
  `mf/harnesses.py` against it.

The CLI is the source of truth for flags in the installed version:

```bash
mf --help
mf search --help
```
