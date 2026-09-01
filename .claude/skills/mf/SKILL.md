---
name: mf
description: Use the mf memoryfield CLI (`mf search`, `mf read`, `mf write`) to check project memory before exploring a codebase cold, and to write or update memoryfield pages through the dedup gate rather than by hand. Use whenever the working directory (or one given to you) has an `mf.sqlite3` index, or when the user asks you to write, update, or check a memoryfield page.
---

# mf: search-first project memory

`mf` indexes a memoryfield (a directory of Markdown pages with
frontmatter) and answers questions with stubs, not pages. Built:
`search`, `read`, `write`, `lint`, `index`, `raw add`. The
numbers behind every rule here, the page-writing conventions, and the
full exit-code contract are in [reference.md](reference.md). Read it
before writing a page.

## Do

- **Search before you explore.** `mf search "<question>" --field <dir>
  --limit 1 --neighbor-limit 0` for a point lookup (about 55 tokens).
  Widen to the defaults (`--limit 3 --neighbor-limit 1`) only when
  `confidence` is `low`/`none` or the question is genuinely broad.
- **Read `confidence` before the results.** `high`: cite the stub.
  `low`: a lead, not an answer; read L1 before citing, and be ready to
  explore instead. `none`: don't cite it.
- **Stub-first.** The summary is written to be the answer. `mf read
  <uuid>` (L1, the answer section) only if the stub isn't enough;
  `--tier L2` or `<uuid>#section` only if L1 isn't.
- **Batch reads for one task** in a single `mf read a b` call; that is
  what records `co_read`.
- **Write a page with `mf write <draft> --field <dir>`, drafting
  outside the field.** It validates, dedup-checks, copies in, and
  indexes in one step. Exit 2 means a near-duplicate was listed: check
  the candidates, then either edit that page in place and `--update
  <uuid>`, or `--force` if it's genuinely different. Retire a page by
  writing its replacement with `supersedes: [old-uuid]`, not by
  deleting it.
- **Run `mf lint <dir>` after writing.** It checks the conventions in
  reference.md (summary shaped as an answer, no tables, no copied SHAs
  or relative dates, links resolve) and index drift. `--check` for CI.

## Don't

- Don't cite a `none`-confidence result.
- Don't pull L2 by default.
- Don't drop a page file into the field and run `mf index` to add it:
  that path has no dedup gate. It exists for bulk imports.
- Don't hand-edit a page and stop. `mf search` refuses a stale index
  (exit 3) until `mf index` runs, or pass `--stale-ok`.
- Don't `cat`/`Read` a page that `mf read` would return: that loses
  the read log and `co_read`.
- Don't call `mf raw add` during a lookup (it's session-end staging).

## Commands

```
mf search "<query>" [--field DIR] [--limit N] [--neighbor-limit N] [--budget N] [--stale-ok] [--json]
mf read <uuid>[#section] [<uuid2>[#section] ...] [--tier L1|L2] [--field DIR] [--json]
mf write <draft-path | -> [--field DIR] [--dest NAME] [--update UUID] [--force] [--json]
mf lint [DIR] [--check] [--all] [--json]
mf index [DIR]
```

Exit codes: `write` 0 written, 1 invalid, 2 dedup-blocked. `search` 0
ok, 1 no field, 3 stale index. `lint --check` 1 on any error or warning.
