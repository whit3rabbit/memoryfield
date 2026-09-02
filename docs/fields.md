# Keeping a field

[Docs](README.md) | [Agents](agents.md) | [CLI](CLI.md) | [Models](models.md) | [Fields](fields.md) | [Architecture](architecture.md) | [Benchmarks](BENCHMARKS.md)

A field is a directory of Markdown pages with frontmatter, plus the
index mf builds from them. This guide covers the life of a field after
the first search: writing pages, keeping the index honest, enforcing
the writing conventions, importing notes you already have, and
exchanging fields with other memoryfield tools.

## What a field is

- Pages are the canonical data: plain Markdown files with a `uuid`, a
  `title`, and a one-line `summary` written as the answer.
  [Architecture, section 1](architecture.md#1-pages-canonical) lists
  every frontmatter field.
- `mf.sqlite3` at the field root is derived from the pages and mostly
  deletable. Three things in it are not: the `reads` log, `co_read`
  weights, and `claims`. [Architecture, section
  2](architecture.md#2-index-derived-mostly-deletable).
- `raw/` is the staging area for session extracts and pointers.
  Nothing indexes it. `mf consolidate --plan` reads it and proposes
  pages.

## Writing pages

New pages go in through `mf write <draft> --field <dir>`, drafting
outside the field. It validates, dedup-checks against near-duplicates,
copies the page in, and indexes it in one step.

Exit 2 means a near-duplicate was flagged: update that page
(`--update <uuid>`) or `--force` if the page really is new. Retire a
page by writing its replacement with `supersedes: [old-uuid]`, not by
deleting the file.

The linter enforces the summary as the answer, one question per page,
verbatim anchors, `## Don't` for negations, and quoted frontmatter.
Those conventions, and why the draft stays outside the field, are in
the [skill reference, "Writing a
page"](../.claude/skills/mf/reference.md#writing-a-page) and
[Architecture, section 5](architecture.md#5-write).

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

## Working with other memoryfield tools

Any spec-conformant field loads as-is:

```bash
mf unpack soapstones.memoryfield.zip ~/soap && mf init ~/soap && mf index ~/soap
```

A spec vector index inside the archive (`nomic-embed-text-v1.5.sqlite3`
or similar) is noted and left alone. mf builds its own. Cal Paterson's
soapstones export is the demo field: `uv run python3
eval/fetch_soapstones.py` downloads it with a pinned checksum.

Going the other way, `mf pack --spec ~/field` writes an archive a spec
reader expects: root-level pages, a `<model>.sqlite3` index in the
spec's schema, no `mf.sqlite3` or `raw/`. Pages in subdirectories are
skipped and listed.

Two rules keep pages readable outside mf. Quote `title`, `summary`,
`created`, `updated`, and anything with `: ` or a leading backtick in
it: mf's parser tolerates the unquoted form, plain YAML readers do
not. Keep filenames to lowercase letters, digits, and hyphens at the
field root. `mf lint` reports both as `spec-*` findings.

## Session capture staging

`mf raw add` appends a freeform extract to `raw/`, and the session-end
hook writes a pointer entry there ([Agents](agents.md#hooks)). `mf
consolidate --plan` reads both and proposes create or review actions
per entry without writing anything. Design and current limits:
[Architecture, section 7](architecture.md#7-session-capture).
