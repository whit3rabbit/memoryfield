---
uuid: mf-eval-corpus-pollution-risk
title: "Why mf's own dogfooding field lives at notes/, not the repo root"
summary: "`mf/indexer.py`'s `_SKIP_DIRS` excludes raw/ but not eval/, so `mf init && mf index` at the MF repo root would silently sweep eval/corpus's 157 real frontmattered calibration pages into the field."
status: active
tags: [dogfooding, indexer, gotcha]
---
## Answer
`mf/indexer.py`'s `_SKIP_DIRS` (`.git`, `.venv`, `venv`, `__pycache__`,
`node_modules`, `.mfgpt`, `raw`) does not include `eval/`. The MF repo's
own `eval/corpus/{codebase,papers}` are 157 real frontmattered
memoryfield pages, the M0/M0.5 calibration fixtures, not real memory.
Running `mf init`/`mf index` at the repo root would silently sweep all
157 of them into whatever field lives there, polluting real search
results with synthetic eval content and reporting nothing wrong (same
silent-failure family as the frontmatter-parser gotchas).

Resolution: mf's own operational memory lives in a dedicated `notes/`
subdirectory instead of the repo root, with its own
`notes/.claude/settings.json` so the Stop/SessionEnd hooks only fire
for a session actually opened at `notes/`.

If a root-level field is ever wanted instead, `eval` needs an entry in
`_SKIP_DIRS` first -- not done, since `notes/` avoids the problem
entirely.

Also found (untouched, not cleaned up here): two untracked, unreferenced
top-level directories, `corpus/` and `queries/`, dated before
`eval/corpus`'s creation and absent from `git ls-files` -- look like
leftovers from before the harness/ -> eval/ rename. Worth a separate
look under the concurrent-session caution (another session may be
using them).
