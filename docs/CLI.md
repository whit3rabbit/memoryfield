# `mf` CLI Reference

[Docs](README.md) | [Agents](agents.md) | [CLI](CLI.md) | [Models](models.md) | [Fields](fields.md) | [Architecture](architecture.md) | [Benchmarks](BENCHMARKS.md)

Complete reference for all `mf` commands, flags, arguments, and JSON output structures.

---

## Command Overview

| Command | Summary |
|---|---|
| [`mf init`](#mf-init) | Initialize a new memoryfield SQLite index (`mf.sqlite3`), then wire a coding agent on a terminal |
| [`mf setup`](#mf-setup) | Install, uninstall, or inspect the instructions, skill, MCP entry, and hooks for a harness |
| [`mf index`](#mf-index) | Incrementally index markdown pages into `mf.sqlite3` |
| [`mf search`](#mf-search) | Perform stub-first semantic search with confidence gating |
| [`mf read`](#mf-read) | Read tiered page sections (`L1`, `L2`, or `#section`) |
| [`mf write`](#mf-write) | Validate, dedup-check, copy in, and index a new page |
| [`mf model`](#mf-model) | Inspect and pre-download supported embedding models |
| [`mf raw`](#mf-raw) | Stage freeform session extracts in `raw/` |
| [`mf lint`](#mf-lint) | Check pages for writing discipline and index drift |
| [`mf pack`](#mf-pack) / [`mf unpack`](#mf-unpack) | Create and extract reproducible `.memoryfield.zip` archives |
| [`mf claim`](#mf-claim) | Atomically claim a slug before page creation (multi-writer) |
| [`mf consolidate`](#mf-consolidate) | Propose create/review actions from staged `raw/` extracts |
| [`mf import`](#mf-import) | Import Claude Code auto-memory or wiki directories |
| [`mf hook`](#mf-hook) | Claude Code session lifecycle hooks (`stop`, `session-end`) |
| [`mf mcp`](#mf-mcp) | Run an MCP server wrapping `search`/`read`/`write`/`raw_add` over stdio |

---

## Commands

### `mf init`

Create an empty `mf.sqlite3` index in the specified field directory, pinning the embedding model and vector dimension.

```bash
mf init [DIR] [--model MODEL] [--no-setup]
```

`DIR` defaults to `notes`, a subdirectory, so the project's own docs never become pages by accident. Every other command that takes a field looks at the cwd first and falls back to `./notes`, so `mf init` followed by `mf search "..."` from the project root just works. When stdin and stdout are a terminal and `DIR` is under the current directory, `mf init` continues into the [`mf setup`](#mf-setup) wizard after creating the index: pick the coding agents that use the project, pick what to install, review the plan, apply. Off a terminal (scripts, CI, hooks) or with `--no-setup`, it prints the one line below and stops, exactly as before.

- **Arguments**:
  - `DIR`: Target field directory (default: `notes`)
- **Options**:
  - `--model <name>`: Embedding model to pin for this field (default: `snowflake-arctic-embed-xs`, 384-d). See [`mf model list`](#mf-model-list) for available models.
  - `--no-setup`: Create the index only; never start the wizard.
- **Exit codes**:
  - `0`: Field initialized successfully (and, on a terminal, the wizard finished or was declined).
  - `1`: `mf.sqlite3` already exists, or the wizard had to skip a file it could not parse.

```console
$ mf init --model snowflake-arctic-embed-xs --no-setup
Initialized empty field at /path/to/myapp/notes/mf.sqlite3 (model snowflake-arctic-embed-xs, 384-d)
```

---

### `mf setup`

Wire mf into a project's coding-agent harness(es): the two-line instruction block, the mf skill, an `mf mcp` server entry, and (Claude Code) the Stop and SessionEnd hooks. Every write is idempotent and every file edit is a patch that leaves the rest of the file alone. Paths and config shapes come from [agent-config](https://github.com/whit3rabbit/agent-config) (vendored schema: `docs/upstream/agent-config-agents.json`), and the markers are that crate's, so it can recognize what mf wrote.

```bash
mf setup                                        # wizard (terminal only)
mf setup install   --harness ID [ID ...] (--instructions|--skill|--mcp|--hooks|--all-surfaces) [--field DIR] [--root DIR] [--dry-run] [--json]
mf setup uninstall --harness ID [ID ...] (--instructions|--skill|--mcp|--hooks|--all-surfaces) [--field DIR] [--root DIR] [--dry-run] [--json]
mf setup status    [--harness ID ...] [--field DIR] [--root DIR] [--json]
mf setup prompt    [--field DIR] [--reference PATH]
```

- **Harness ids**, in menu order: `claude`, `codex`, `cursor`, `copilot`, `opencode`, `gemini`, `antigravity`, `windsurf`, `amp`, `pi`. The other fifteen ids in the schema are shown in the wizard as "not yet".
- **Surfaces per harness** (project-local scope):
  - `instructions`: a fenced block in `CLAUDE.md` (claude), `AGENTS.md` (codex, opencode, amp, pi), `GEMINI.md` (gemini), `.github/copilot-instructions.md` (copilot), or a standalone `.agents/rules/mf.md` (antigravity) / `.windsurf/rules/mf.md` (windsurf). Cursor has no project instruction file upstream.
  - `skill`: `SKILL.md` and `reference.md` under the harness's skills directory (`.claude/skills/mf/`, `.agents/skills/mf/` for codex, antigravity, and amp, `.cursor/skills/mf/`, `.github/skills/mf/`, `.opencode/skills/mf/`, `.gemini/skills/mf/`, `.windsurf/skills/mf/`, `.pi/skills/mf/`).
  - `mcp`: an `mf` entry running `mf mcp --field DIR`. `mcpServers` JSON in `.mcp.json` (claude and copilot share it), `.cursor/mcp.json`, `.gemini/settings.json`, `.agents/mcp_config.json`, `.windsurf/mcp_config.json`, `.amp/settings.json`, `.pi/mcp.json`; the `mcp` key in `opencode.json`; a `[mcp_servers.mf]` table in `.codex/config.toml`. The server ships with the package, so the entry works as soon as it is written.
  - `hooks`: Claude Code only, `.claude/settings.json`, `Stop` and `SessionEnd` groups running `mf hook ... --field DIR`.
  - The field's `.gitignore` (`mf.sqlite3`, `mf.sqlite3-*`) is always written on install and removed on uninstall.
- **Options**:
  - `--field <dir>`: Field directory relative to `--root` (default: `notes`). `.` means the project root is the field, and the generated commands then carry no `--field`.
  - `--root <dir>`: Project root (default: cwd). Harness files are written here.
  - `--all-surfaces`: Every surface the harness supports.
  - `--dry-run`: Print the plan, write nothing.
  - `--reference <path>`: For `prompt`, the installed skill's `reference.md` the prompt should point at (default: `.claude/skills/mf/reference.md`).
- **Actions** in the plan: `create`, `patch`, `unchanged`, `remove`, `SKIP`. A file that exists but cannot be parsed (a JSONC `opencode.json`, a `[mcp_servers.mf]` table with other content, a `SKILL.md` that is not mf's, an unbalanced fence) is skipped with the reason and left byte-identical. Uninstall removes a file only when nothing but mf's content was in it.
- **Status states** per harness and surface: `installed`, `absent`, `unmanaged` (present, not what mf writes), `malformed` (cannot parse), `unsupported`.
- **Exit codes**:
  - `0`: Applied, or dry run, or declined in the wizard.
  - `1`: At least one file was skipped; bare `mf setup` outside a terminal; no surface given; field outside the root.

```console
$ mf setup install --harness claude codex --all-surfaces --dry-run
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

JSON shape for `install`/`uninstall`: `{"mode", "dry_run", "root", "field", "actions": [{"path", "surface", "harnesses", "action", "note"}], "warnings": [...], "failed"}`. For `status`: `{"root", "field", "field_initialized", "entries": [{"harness", "surface", "path", "state"}]}`.

---

### `mf index`

A schema v2 index is migrated in place on the way (`migrated index v2 ->
v3` is printed): the derived tables are rebuilt, the reads log, `co_read`
weights, and claims are kept. Two files carrying one uuid are reported
on stderr, neither is indexed, and the exit code is 1. Files that have
frontmatter but fail to parse (or are not UTF-8) are reported and
skipped rather than aborting the run.

Walk a field directory and incrementally index all valid Markdown pages. Skips unchanged files (matching SHA256) and prunes index entries for deleted files.

```bash
mf index [DIR]
```

- **Arguments**:
  - `DIR`: Field directory (default: the cwd if it is a field, else `./notes`)
- **Exit codes**:
  - `0`: Indexing complete.
  - `1`: `mf.sqlite3` not found (run `mf init` first).

```console
$ mf index ~/field
75 upserted, 0 unchanged, 0 deleted
```

---

### `mf search`

Search indexed pages using dense semantic retrieval with an integrated FTS confidence gate. Returns lean result stubs rather than full page bodies.

```bash
mf search "<query>" [--field DIR] [--limit N] [--neighbor-limit N] [--budget N] [--stale-ok] [--json]
```

- **Arguments**:
  - `query`: The search query text.
- **Options**:
  - `--field <dir>`: Field directory (default: the cwd if it is a field, else `./notes`).
  - `--limit <n>`: Number of top result stubs to return (default: `2`).
  - `--neighbor-limit <n>`: Number of neighbor stubs per result (default: `0`).
  - `--budget <n>`: Maximum total token cap for the output.
  - `--stale-ok`: Return results even if on-disk files changed since last indexing (marked `stale`).
  - `--json`: Format output as JSON.
- **Exit codes**:
  - `0`: Search completed successfully. Check the `confidence` field before citing.
  - `1`: No field at `--field`, a schema that needs `mf index`, or a bad flag value (`--limit` under 1, negative `--neighbor-limit` or `--budget`).
  - `3`: Stale index detected (a file changed or was removed on disk; re-run `mf index` or pass `--stale-ok`).

On a field with no vectors yet, the model is not loaded and FTS alone
answers. `--budget` keeps every stub that fits in rank order (a large
rank-1 stub does not hide a small rank-2 one) and reports `none` when
nothing fits.

```console
$ mf search "how do we roll back a deploy" --field ~/field
confidence: low
- [code-deploy-rollback-cmd] Deploy: how to roll back a bad release
    `kubectl rollout undo deployment/<service>`; rollback is a forward operation and takes ~90 seconds end-to-end.
- [code-deploy-pre-checklist] Deploy: pre-deploy checklist
    Tests green, migrations applied to staging, dashboards reviewed, on-call notified, rollback plan documented.
```

---

### `mf read`

Read tiered content from one or more pages. Defaults to the answer-first L1 section.

```bash
mf read <uuid>[#section] ... [--field DIR] [--tier L1|L2] [--json]
```

- **Arguments**:
  - `refs`: One or more page UUIDs, optionally with a `#section-slug` anchor.
- **Options**:
  - `--tier <L1|L2>`: Escalation tier. `L1` returns the first section (default); `L2` returns all subsequent sections.
  - `--field <dir>`: Field directory (default: the cwd if it is a field, else `./notes`).
  - `--json`: Output as JSON.

```console
$ mf read code-deploy-rollback-cmd --field ~/field
[code-deploy-rollback-cmd (L1)] Deploy: how to roll back a bad release
`kubectl rollout undo deployment/<service>` re-deploys the
previous image. Takes ~90s for full pod replacement at our scale.
```

L1 is any prose before the first `##` plus the first `##` section. L2 is
everything after that.

---

### `mf write`

Validate frontmatter, run the near-duplicate embedding check, copy the draft into the field, and index it in one step.

```bash
mf write <path> [--field DIR] [--dest NAME] [--update UUID] [--force] [--json]
```

- **Arguments**:
  - `path`: Path to draft markdown file (outside or inside field) or `-` for stdin.
- **Options**:
  - `--field <dir>`: Field directory (default: the cwd if it is a field, else `./notes`).
  - `--dest <name>`: Destination filename inside the field (default: draft filename).
  - `--update <uuid>`: UUID this write intentionally updates (bypasses dedup check).
  - `--force`: Bypass near-duplicate check.
  - `--json`: Output result as JSON.
- **Exit codes**:
  - `0`: Page successfully validated and indexed.
  - `1`: Frontmatter validation failed.
  - `2`: Near-duplicate detected (cosine distance at or under 0.10). Use `--update <uuid>` or `--force`.

`--dest` must stay inside the field and outside directories `mf index`
never walks (`raw/`, dot-directories). The copy-in is atomic: the file
takes its final name only after it is indexed.

```console
$ mf write /tmp/draft.md --field ~/field
Wrote code-new-deploy to draft.md
```

JSON shape: `{"written": bool, "uuid": str, "path"?: str,
"duplicates"?: [{"uuid", "title", "summary", "distance"}], "warning"?: str}`.

---

### `mf model`

Manage embedding models used by `mf init`.

#### `mf model list`

List all available embedding models, output dimensions, download sizes, query latency, and local cache status.

```bash
mf model list [--json]
```

```console
$ mf model list
Model                          Dim    Size       Speed     Cached   Description
---------------------------------------------------------------------------------------------------------
* snowflake-arctic-embed-xs    384    ~170 MB    0.9 ms    yes      Default: ultra-fast 384-d, high accuracy (0.950 top-1)
  snowflake-arctic-embed-s     384    ~255 MB    1.8 ms    yes      Highest blind accuracy (0.975 top-1), fast 384-d
  bge-small-en-v1.5            384    ~130 MB    2.4 ms    yes      Compact, balanced retrieval (0.950 top-1)
  all-MiniLM-L6-v2             384    ~170 MB    3.1 ms    yes      Ultra-lightweight baseline (0.925 blind top-1)
  jina-embeddings-v2-small-en  512    ~250 MB    0.9 ms    yes      512-d output, 8192-token context window
  bge-base-en-v1.5             768    ~420 MB    5.9 ms    yes      768-d baseline (0.925 top-1)
  nomic-embed-text-v1.5        768    ~520 MB    4.6 ms    yes      768-d asymmetric model, 8192-token context
  bge-large-en-v1.5            1024   ~2.5 GB    12.6 ms   yes      1024-d high-capacity model (0.950 top-1)

* = default model for `mf init`
```

#### `mf model install`

Pre-download and warm up model weights into the local cache ahead of time.

```bash
mf model install <model_name> [--json]
```

```console
$ mf model install bge-small-en-v1.5
Downloaded and ready: bge-small-en-v1.5 (384-d, ~130 MB).
```

---

### `mf raw`

Stage freeform session extracts in `raw/` without indexing them.

```bash
mf raw add [text] [--field DIR] [--json]
```

- **Arguments**:
  - `text`: Freeform text to append (reads from stdin if omitted).
- **Options**:
  - `--field <dir>`: Field directory (default: the cwd if it is a field, else `./notes`).
  - `--json`: Output result as JSON.

```console
$ mf raw add "Encountered timeout on redis cluster during shard rebalancing" --field ~/field
Appended to /home/me/field/raw/20260903T111702381618Z.md
```

JSON shape: `{"written": bool, "path": str}`.

---

### `mf lint`

Enforce writing conventions (answer-first summaries, headings under token limits, link integrity) and check index synchronization.

```bash
mf lint [DIR] [--check] [--all] [--json]
```

- **Arguments**:
  - `DIR`: Field directory (default: the cwd if it is a field, else `./notes`).
- **Options**:
  - `--check`: Exit with code 1 if any `error` or `warning` is found (ideal for CI/git pre-commit).
  - `--all`: Also print `info`-level suggestions.
  - `--json`: Output as JSON.
- **Spec-conformance codes** (what readers other than mf would reject,
  `docs/upstream/SPEC.md`): `spec-yaml` (warning: frontmatter that
  plain YAML rejects, typically an unquoted `Topic: question` title or
  a backtick-leading summary), `spec-filename` (warning: not
  `[a-z0-9-]`), `spec-dates` (info when `created`/`updated` are
  missing, error when one is an unquoted datetime), `spec-subdir`
  (info: spec readers only index root-level pages).
- **Freshness code**: `stale-updated` (info: `updated`, falling back to
  `created`, is more than 180 days old. A nudge to review the page, not
  a check that its content is still accurate).

```console
$ mf lint --check ~/field
75 pages: 0 errors, 0 warnings, 340 info (--all to show info)
```

JSON shape: `{"pages": int, "errors": int, "warnings": int, "info": int,
"findings": [{"severity", "code", "filename", "uuid", "message"}]}`.
With an index present, `orphan-claim` (info) names claims whose slug has
no page on disk.

---

### `mf pack`

Create a reproducible `.memoryfield.zip` archive with a SHA256 sidecar.

```bash
mf pack [DIR] [--out PATH] [--no-index] [--no-raw] [--spec] [--json]
```

- Archives field contents with normalized timestamps and POSIX paths for reproducible byte hashes.
- Generates `<name>.memoryfield.zip.sha256`.
- `--spec`: an archive for readers that are not mf, per the vendored
  spec (`docs/upstream/SPEC.md`): root-level pages with `[a-z0-9-]`
  filenames, root-level non-page files, and a `<model_code>.sqlite3`
  vector index in the spec's schema (whole-file embedding). Leaves
  out `mf.sqlite3`, `raw/`, and pages in subdirectories, and lists
  the skipped pages.

### `mf unpack`

Verify and extract a `.memoryfield.zip` archive.

```bash
mf unpack <ZIP> [DEST] [--sha256 HEX] [--force] [--json]
```

- Verifies SHA256 integrity before extraction.
- Resolves field-relative database paths automatically.
- Reads a spec archive (such as Cal Paterson's soapstones export)
  as-is. A spec `<model>.sqlite3` index is noted, not read. Run
  `mf init` then `mf index` afterwards.

---

### `mf claim`

Atomically claim a page slug in multi-writer environments before drafting.

```bash
mf claim <slug> --by <writer> [--release] [--field DIR] [--json]
```

- **Arguments**:
  - `slug`: Filename stem to claim.
  - `--by <writer>`: Identity of claiming agent/user.
  - `--release`: Drop your own claim on the slug. Another writer's claim is left alone and reported.
- **Exit codes**:
  - `0`: Claim successful or already owned by caller. With `--release`: released, or nothing was claimed.
  - `2`: Slug already claimed by another writer.

Claims never expire on their own. `mf lint` reports `orphan-claim` for a claim with no page behind it.

```console
$ mf claim new-deploy --by alice --field ~/field
Claimed 'new-deploy' for alice at 2026-09-03T11:17:02.851821+00:00
$ mf claim new-deploy --by bob --field ~/field
mf claim: 'new-deploy' already claimed by alice at 2026-09-03T11:17:02.851821+00:00 (under an hour ago); look up that page and use `write --update` instead
$ mf claim new-deploy --by alice --release --field ~/field
Released 'new-deploy' (was claimed by alice at 2026-09-03T11:17:02.851821+00:00)
```

JSON shape: `{"slug": str, "claimed": bool, "claimed_by": str, "claimed_at": str, "released"?: true}`.

---

### `mf consolidate`

Inspect staged session notes in `raw/` and propose new pages, edits, or review actions without modifying the index directly.

```bash
mf consolidate --plan [--field DIR] [--threshold FLOAT] [--json]
```

`--threshold` is the cosine distance under which an existing page makes
an entry a `review` rather than a `create` (default 0.10, untuned).
Entries are embedded on the document side, the same side pages are.

---

### `mf import`

Import existing documentation or note repositories as memoryfield pages.

```bash
mf import claude-memory <dir> [--field DIR] [--dry-run] [--json]
mf import wiki <dir> [--field DIR] [--dry-run] [--json]
```

- `claude-memory`: Converts Claude Code `MEMORY.md` and topic files into pages under `<field>/claude-memory/`.
- `wiki`: Converts index.md-style wikis with subdirectories into flattened pages under `<field>/wiki/`.

---

### `mf hook`

Handlers invoked by Claude Code hooks at session lifecycle events.

```bash
mf hook stop        [--field DIR]   # Prompts agent to capture learnings before finishing session
mf hook session-end [--field DIR]   # Stages session metadata pointer into raw/ (<0.25s runtime)
```

Claude Code runs hooks with `cwd` set to the project root. `--field DIR` joins `DIR` onto that cwd, so a field kept in a subdirectory (`notes/`) still fires. Without it, only a project whose root is the field does anything. `mf setup install --hooks` writes the flag for you.

---

### `mf mcp`

Run an MCP server (stdio transport) exposing `search`, `read`, `write`, and `raw_add` as tools.

The `mcp` package is a core dependency (ROADMAP.md 5.4), so a plain `uv tool install memoryfield` or `pipx install memoryfield` includes the server and the MCP entry [`mf setup`](#mf-setup) writes works as is. The server stack is imported only when `mf mcp` runs; every other command leaves it unloaded. If the package is missing from a broken install, `mf mcp` exits 1 with a message naming the reinstall command, not a traceback.

```bash
mf mcp [--field DIR]
```

Each tool wraps the same library function the CLI command calls, and every tool takes an optional `field` argument resolved against the server process's cwd. A call that leaves it out uses the server's `--field` (default `"."`), so a project-level MCP entry can pin a subdirectory field with `mf mcp --field notes` and the agent never has to know where the field lives. `mf setup install --mcp` writes that entry.

- `search(query, field=None, limit=2, neighbor_limit=0, budget=None, stale_ok=False)`: same gate and ranking as `mf search`. Returns `SearchResult.as_dict()`.
- `read(refs, field=None, tier=None)`: `refs` is a list of `uuid` or `uuid#section`. Returns `{"results": [ReadResult.as_dict(), ...]}` (the CLI's own `--json` output is a bare array here, but MCP structured output must be a JSON object, so it's wrapped under `results`).
- `write(text, dest, field=None, update=None, force=False)`: `text` is a draft's full frontmatter and body, `dest` is the filename to write it under inside the field. Returns `WriteResult.as_dict()`. A dedup-blocked draft comes back with `written: false` and a `duplicates` list, not an error.
- `raw_add(text, field=None)`: appends a session extract to `raw/`. Returns `RawAddResult.as_dict()`.

A caller-avoidable failure (no field at that path, a stale index, a ref that doesn't exist, a draft that fails validation, empty raw text, a stale result without `stale_ok`) is raised as an MCP `ToolError`. The message reaches the model as a normal tool result, not a crash.
