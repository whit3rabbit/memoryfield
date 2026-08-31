# mf — plan

Working name `mf`. Context-frugal memoryfield tool. Reads and writes
memoryfield-spec pages unchanged, adds a derived SQLite index with hybrid
search, returns stubs instead of pages, and pushes every judgment call to the
agent that is already running. The tool itself never calls an LLM.

---

## 1. What it has to do

Three numbers drive the design:

- Tokens injected at session start. Target: under 200.
- Tokens consumed per lookup. Target: under 1,200, with most lookups ending
  at the stub stage.
- Tool calls per lookup. Target: 2 (search, read), same as Cal's design.

Everything else — the schema, the models, the writing rules — serves those
three.

---

## 2. Architecture

Five layers. The first is the spec; the rest are derived or conventional.

**Pages (canonical).** Memoryfield-spec Markdown with frontmatter. Extended
fields, all optional so plain memoryfields still load:

```
uuid, title, created, updated          # spec
summary:      one line, written as the answer, not the topic
status:       active | superseded | contested
supersedes:   [uuid]
contradicts:  [uuid]
depends_on:   [uuid]
tags:         [..]
source:       url or path                # citation slot
writer:       agent-or-person id
```

Body convention: first section is L1 (answer-first, 150–300 tokens); later
sections are L2. Sections are addressable as `uuid#slug`.

**Index (derived, deletable).** One SQLite file, `mf.sqlite3`, inside the
field:

```
pages   (uuid PK, filename, title, summary, status, tokens, sha256, updated, writer)
sections(uuid, slug, ordinal, byte_start, byte_end, tokens)
fts     -- FTS5 over title, summary, body (full page)
vec     -- sqlite-vec, embedding of title+summary+L1 only, model-tagged
links   (src, dst, kind, weight)      -- kind: supersedes|contradicts|depends_on|co_read
claims  (slug, claimed_by, claimed_at) -- for multi-writer create/update resolution
```

Why this split: dense on L0+L1 retrieves on what a page is *for*; FTS over
the full body catches the port number in paragraph six. Neither is precomputed
against the other — kNN neighbors are computed at query time from `vec`, so
they never go stale. Only typed links and co-reads are stored.

**Retrieval.** `search` runs FTS5 and vector queries, fuses with reciprocal
rank fusion, optionally reranks the top 20 with a cross-encoder, then returns
the top-k as stubs (uuid, title, summary, status, tokens) with up to n
neighbor stubs each (typed links first, then kNN, then co_read). Superseded
pages are returned only as a `superseded_by` pointer on the winner. Output is
JSON or a compact text table; the agent never sees a body unless it asks.

**Read.** `read uuid[#section] --tier L1|L2` returns exactly that slice and
logs the read. Two uuids read in one call increments `co_read` between them.

**Write.** `write` validates frontmatter, runs a dedup search against the
proposed title+summary, and refuses (exit code + list of near-duplicates)
unless `--force` or `--update uuid`. `claim slug` does an atomic conditional
insert so parallel writers degrade from create to update. `raw add` appends a
session extract to `raw/` (a subdirectory the spec says implementations must
not index). `consolidate --plan` reads `raw/`, searches for each candidate
memory, and emits a JSON plan of create / update / supersede actions with the
evidence; the agent executes the plan with `write`. `lint` reports hash
mismatches, active pages that a superseded page points at, orphans, pages
over token budget, tables in bodies, copied-state patterns (SHAs, counts,
"last week"), and missing `source`.

**Pack.** `pack` produces `name.memoryfield.zip` plus sha256, index included.
`unpack` verifies.

---

## 3. Holes from the review, and where each is closed

| Hole | Fix in this design |
|---|---|
| qmd chunks and returns chunk lists | Page is the embedding unit; search returns stubs; no chunking anywhere |
| Always-loaded index is one-hop spidering | Nothing loaded but a ~10-line topic list and the search affordance |
| Consolidation is the rejected pipeline | It runs in-band in the host agent via the skill; the tool only emits a plan |
| Git doesn't fix divergent creation | `claims` table + `write` dedup gate; git kept only as transport and history |
| Whole-page reads cost 10K tokens per lookup | Stub-first, then L1, section-level reads |
| Negation embeds like affirmation | `status` and `supersedes` are structured; `## Don't` is a lint-enforced section |
| Stale embeddings | `index` is incremental on sha256; `lint` flags mismatches; `search` refuses on mismatch unless `--stale-ok` |
| Bad nomic defaults (num_ctx, prefixes) | Embedder runs in-process with the correct task prefixes; no Ollama |

---

## 4. Stack

- **Language: Python for v1, distributed with `uv tool install`.** One package
  manager instead of Cal's four. `sqlite-vec` and FTS5 are in-process;
  embeddings via `fastembed` (ONNX runtime), so no model server. The CLI
  contract is the product; if it sticks, a Rust port (`rusqlite` +
  `fastembed-rs`) gives a single static binary. Do not start in Rust: the
  schema and the writing conventions will change during M0–M2 and Python
  iterates faster.

- **Why not TypeScript:** agents shell out to it fine, but ONNX embedding on
  Node is a rougher path than Python and the reranker options are thinner.

**Models, all local, all optional beyond the embedder:**

| Role | Default | Alternate | Notes |
|---|---|---|---|
| Embedder | `nomic-embed-text-v1.5` | `embeddinggemma-300m` | ONNX, 270 MB, 768-d (Matryoshka to 256-d for storage). Spec-required model code stays `nomic-embed-text-v1.5` so existing fields interoperate. |
| Reranker | none | `bge-reranker-v2-m3` or `Qwen3-Reranker-0.6B` ONNX | Turn on when P@3 in the eval harness is under ~0.8; it pays for itself in unread pages. |
| LLM | none | — | Extraction and consolidation are done by the host agent. |

**Hardware floor:** CPU laptop, ~1 GB RAM without reranker, ~2.5 GB with.
Index rebuild for 1,000 pages on CPU: roughly a minute.

**Surfaces, in priority order:**

1. **CLI** — source of truth. Every command has `--json`. Agents use it
   through bash.
2. **SKILL.md** — teaches search-before-read, stub-first reading, the page
   conventions, and the end-of-session `raw add` step. Ships in the repo,
   installable with `npx skills add` or by copying.
3. **MCP server** — thin wrapper around the CLI for hosts without a shell
   (Cursor, desktop chat apps). Exposes `search`, `read`, `write`, `raw_add`.
   Same JSON.

---

## 5. Writing conventions (enforced by `lint`, taught by the skill)

- `summary` is the answer. "Integration tests: `make test-integration`; needs
  `DATABASE_URL`" not "Notes on testing."
- First section answers; rationale and history follow.
- 300–800 tokens per page. 8 KB is a ceiling.
- One page per question someone would ask, not per topic.
- Verbatim anchors for stable values (commands, hostnames, error strings).
  Pointers for moving values (SHAs, counts).
- Negations under `## Don't` and via `status`/`supersedes`, never only in
  prose.
- `key: value` lines instead of tables. No headers under 300 tokens. Code
  fences only around real commands.
- ISO dates in frontmatter; no relative time in bodies.
- `source` filled whenever the memory came from somewhere.

---

## 6. Expected savings

Modeled, not measured. Build the harness in M0 before trusting any of this.

| Cost | Cal's default | mf | Ratio |
|---|---|---|---|
| Session-start injection (200-line index pattern) | 2,000–3,000 tokens | ~200 | 10–15× |
| Lookup answered at stub stage | search 20 titles (~300) + read 3 pages (~4,500) | ~600 | 7× |
| Lookup needing two L1 reads | ~7,800 (search + 5 pages) | ~1,100 | 7× |
| Lookup needing one full L2 page | ~7,800 | ~2,300 | 3× |
| Wrong-page reads per lookup | ~1 in 3 without rerank; ~1 in 8 with rerank | fewer, each avoided read ≈ 1,500 |

Amortized against this: consolidation costs the host agent roughly the size of
`raw/` plus the pages it touches, once per N sessions. At ten sessions per
consolidation and 2K tokens per raw extract, that is ~20K tokens per cycle, or
~2K per session — less than one avoided full-page read.

**What the harness should measure:** P@3 and R@5 on a labeled query set,
tokens from query to correct answer, and the fraction of lookups that end at
the stub stage. Compare grep-only, FTS-only, dense-only, hybrid, hybrid+rerank.

---

## 7. Use cases and what changes per case

**Personal agent memory.** The default profile. Pages are lessons,
preferences, decisions. `raw add` at session end, consolidate weekly.

**Codebase memory.** Pages hold what the code doesn't say: why a decision
was made, the gotcha that cost an afternoon, the command that actually works.
Anchors are file paths and symbols, so FTS carries most of the load. Do not
store what `/doctor`-style trimming would cut (directory layouts, dependency
lists). Integration: one line in AGENTS.md or CLAUDE.md saying "run
`mf search` before exploring"; a post-commit hook runs `mf index`; `co_read`
between a page and a file path is cheap and useful.

**Research papers.** `raw/` holds the source PDFs or clipped text. Pages are
claims, one per claim, with `source` set to DOI or URL and `tags` for
method/dataset. `contradicts` is the link kind that earns its keep here;
`supersedes` handles retractions and revised results. The stub summary carries
the number or finding, so a literature question often ends at the stub stage.
Pair with Karpathy-style ingest: the agent reads the paper, writes claim
pages, `write` dedups against existing claims.

**Team or shared wiki.** Git as transport, `writer` set per agent or person,
`claim` before create, consolidation run by a designated agent. The
`contested` status exists for this case: two writers disagree, neither wins
by default, a human or a later source resolves it.

**Runbooks and incidents.** `## Don't` sections and verbatim commands are the
whole value. Page per failure mode. `supersedes` when a fix changes.

Tuning per case: what gets embedded (L1 only vs. L1 + first 500 tokens of
body), page size target, which link kinds are shown by default, whether the
reranker is on.

---

## 8. Integration

- **Claude Code.** Skill in `.claude/skills/mf/`; a `SessionEnd` hook that
  runs `mf raw add --from-transcript`; a line in CLAUDE.md pointing at the
  skill. Import existing auto-memory with `mf import claude-memory <dir>`
  (MEMORY.md lines become stubs, topic files become pages).
- **Codex / any AGENTS.md reader.** Two lines in AGENTS.md: search before
  exploring, `raw add` before finishing.
- **Cursor, desktop chat apps.** MCP server.
- **OpenClaw / Hermes-style harnesses.** CLI through their shell tool;
  SKILL.md is portable.
- **Obsidian.** Pages are plain Markdown with frontmatter; Dataview reads
  `status` and `tags`. `[[wikilinks]]` are tolerated but not indexed as links
  (uuid links are canonical).
- **Existing memoryfields.** Load unchanged; `mf index` adds the extra tables;
  `mf pack` emits a spec-valid zip.
- **Existing Karpathy wikis.** `mf import wiki <dir>` maps `index.md` entries
  to summaries and tolerates subdirectories by flattening filenames.
- **CI.** `mf lint --check` as a pre-commit or PR check on shared fields.

---

## 9. Milestones

- **M0 — harness.** A labeled corpus (~150 pages, ~60 queries) in two
  domains (codebase, papers). Baselines for grep, FTS, dense, hybrid. Token
  accounting per lookup. Nothing else ships until this exists.
- **M1 — read path.** `init`, `index` (incremental), `search` (hybrid,
  stubs, neighbors, budget), `read` (tier, section). Skill v0.
- **M2 — write path.** `write` with dedup gate, `raw add`, `lint`,
  `pack`/`unpack`.
- **M3 — hooks and imports.** Claude Code hook, AGENTS.md snippet,
  `import claude-memory`, `import wiki`.
- **M4 — reranker and eval gate.** Optional reranker; harness decides the
  default.
- **M5 — consolidation and multi-writer.** `consolidate --plan`, `claims`,
  `contested` status, `co_read`.
- **M6 — MCP server, then packaging.** Rust port only if install friction is
  the top complaint.

---

## 10. Open risks

- `co_read` needs the read tool to be the read path. An agent that `cat`s a
  page bypasses it. Acceptable; the signal is opportunistic.
- Dedup at write time is an LLM judgment the tool can only inform. The gate
  returns candidates; the agent decides.
- Stub-first reading depends on summaries being written as answers. The
  linter can check shape, not quality. The harness should track "ended at
  stub stage" as a proxy.
- Reranker latency on CPU (~1–2 s for 20 candidates) may not be worth it for
  small fields. The harness decides.
