# `mf` CLI Reference

[Docs](README.md) | [Agents](agents.md) | [CLI](CLI.md) | [Models](models.md) | [Fields](fields.md) | [Architecture](architecture.md) | [Benchmarks](BENCHMARKS.md)

Complete reference for all `mf` commands, flags, arguments, and JSON output structures.

---

## Command Overview

| Command | Summary |
|---|---|
| [`mf init`](#mf-init) | Initialize a new memoryfield SQLite index (`mf.sqlite3`) |
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

---

## Commands

### `mf init`

Create an empty `mf.sqlite3` index in the specified field directory, pinning the embedding model and vector dimension.

```bash
mf init [DIR] [--model MODEL]
```

- **Arguments**:
  - `DIR`: Target field directory (default: `.`)
- **Options**:
  - `--model <name>`: Embedding model to pin for this field (default: `snowflake-arctic-embed-xs`, 384-d). See [`mf model list`](#mf-model-list) for available models.
- **Exit codes**:
  - `0`: Field initialized successfully.
  - `1`: `mf.sqlite3` already exists.

```console
$ mf init ~/field --model snowflake-arctic-embed-xs
Initialized empty field at ~/field/mf.sqlite3 (model snowflake-arctic-embed-xs, 384-d)
```

---

### `mf index`

Walk a field directory and incrementally index all valid Markdown pages. Skips unchanged files (matching SHA256) and prunes index entries for deleted files.

```bash
mf index [DIR]
```

- **Arguments**:
  - `DIR`: Target field directory (default: `.`)
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
  - `--field <dir>`: Field directory (default: `.`).
  - `--limit <n>`: Number of top result stubs to return (default: `2`).
  - `--neighbor-limit <n>`: Number of neighbor stubs per result (default: `0`).
  - `--budget <n>`: Maximum total token cap for the output.
  - `--stale-ok`: Return results even if on-disk files changed since last indexing (marked `stale`).
  - `--json`: Format output as JSON.
- **Exit codes**:
  - `0`: Search completed successfully.
  - `3`: Stale index detected (a file changed or was removed on disk; re-run `mf index` or pass `--stale-ok`).

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
  - `--field <dir>`: Field directory (default: `.`).
  - `--json`: Output as JSON.

```console
$ mf read code-deploy-rollback-cmd --field ~/field
# Deploy: how to roll back a bad release

`kubectl rollout undo deployment/<service>`; rollback is a forward operation and takes ~90 seconds end-to-end.
```

---

### `mf write`

Validate frontmatter, run the near-duplicate embedding check, copy the draft into the field, and index it in one step.

```bash
mf write <path> [--field DIR] [--dest NAME] [--update UUID] [--force] [--json]
```

- **Arguments**:
  - `path`: Path to draft markdown file (outside or inside field) or `-` for stdin.
- **Options**:
  - `--field <dir>`: Target field directory (default: `.`).
  - `--dest <name>`: Destination filename inside the field (default: draft filename).
  - `--update <uuid>`: UUID this write intentionally updates (bypasses dedup check).
  - `--force`: Bypass near-duplicate check.
  - `--json`: Output result as JSON.
- **Exit codes**:
  - `0`: Page successfully validated and indexed.
  - `1`: Frontmatter validation failed.
  - `2`: Near-duplicate detected (cosine distance $\le 0.10$). Use `--update <uuid>` or `--force`.

```console
$ mf write /tmp/draft.md --field ~/field
Wrote code-new-deploy to ~/field/new-deploy.md and indexed (384-d)
```

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
  - `--field <dir>`: Field directory (default: `.`).
  - `--json`: Output result as JSON.

```console
$ mf raw add "Encountered timeout on redis cluster during shard rebalancing" --field ~/field
Appended to ~/field/raw/2026-09-01T20-00-00Z.md
```

---

### `mf lint`

Enforce writing conventions (answer-first summaries, headings under token limits, link integrity) and check index synchronization.

```bash
mf lint [DIR] [--check] [--all] [--json]
```

- **Arguments**:
  - `DIR`: Target field directory (default: `.`).
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

```console
$ mf lint --check ~/field
0 errors, 0 warnings
```

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
mf claim <slug> --by <writer> [--field DIR] [--json]
```

- **Arguments**:
  - `slug`: Filename stem to claim.
  - `--by <writer>`: Identity of claiming agent/user.
- **Exit codes**:
  - `0`: Claim successful or already owned by caller.
  - `2`: Slug already claimed by another writer.

---

### `mf consolidate`

Inspect staged session notes in `raw/` and propose new pages, edits, or review actions without modifying the index directly.

```bash
mf consolidate --plan [--field DIR] [--json]
```

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
mf hook stop          # Prompts agent to capture learnings before finishing session
mf hook session-end   # Stages session metadata pointer into raw/ (<0.25s runtime)
```
