# mf — tasklist and phases

State as of this writing: **Phase 0 is closed.** M0/M0.5 harness built and committed (corpus builder, grep/TF-IDF/FTS5/dense/hybrid baselines, bootstrap CIs, stub-end-given-hit, no-answer and paraphrase query sets), all 12 baseline×domain rows run, REPORT.md written with CIs and the corrected given-hit metric. Established findings: embedding input matters more than model choice (27-point swing from title+summary+L1 vs summary-only; 8 points from the BGE query prefix); benchmark is at ceiling (~0.94–0.99 everywhere); FTS-first survives on operational grounds, not quality; dense is co-equal and gets sequenced, not fused; abstention is the only axis where baselines still differ. Open debt: `stub_end_given_hit_rate` was silently broken until this pass (see 0.3 note), 0.4's hand spot-check and 0.5's upstream email are still unsent, score gate uncalibrated, no real-agent trial, no blind query set. `docs/architecture.md` now holds the standing schema/retrieval reference so Phase 1 doesn't have to re-derive it from PLAN.md each time.

Ordering rule carried over from the killed-process incident: compute time and uncommitted state never overlap. Anything marked (commit) lands before the next long-running task starts.

---

## Phase 0 — close out M0.5 (half a day)

- [x] **0.1 Commit pending bug-fix batch** (commit). Done across `67e4a2b`..`7c724a8`; superseded-headline framing landed in the M0.5 report rather than a commit message, which reads fine in context.
- [x] **0.2 Run the two remaining rows** — `dense_bge_papers`, `hybrid_papers`. Both present in `harness/results/` and `summary.json`. Confirmed moot at ceiling as expected.
- [x] **0.3 Write REPORT.md** from report.py output plus narrative. Required structure, checked against the current [M0.5_REPORT.md](M0.5_REPORT.md):
  - Headline: what you embed matters more than which model (the two swing numbers). Present.
  - Second: ceiling caveat. Present.
  - Third: scope condition (write discipline, lint load-bearing). The lint-load-bearing framing lives in [docs/architecture.md](docs/architecture.md) and CLAUDE.md gotcha 16 rather than duplicated inline in the report, consistent with the report's own no-duplication convention.
  - "What changed and why" section. Present.
  - Findings 5 and 7 fixed. Present; finding 7 ("hybrid has nothing left to fuse") reflects the post-fix data where hybrid is no longer a net loss.
  - All tables with CIs; stub-end reported conditional on hit; provisional rows marked. **Was not actually true until this pass** — `stub_end_given_hit_rate` incremented its hit counter unconditionally on every retrieval hit, so it evaluated to a flat `1.0` in all 12 result files and the report used the ungated `stub_end_rate` instead. Fixed in `run_baselines.py`, all 12 rows rerun, CIs and the corrected given-hit rate (0.69–0.87 across baselines) now render in the report tables. See CLAUDE.md gotcha 17. No provisional rows remain; all 12 baseline×domain combos are complete.
- [ ] **0.4 Stub-end de-bias check.** De-biased judgments exist (`harness/stub_sufficiency_debiased.jsonl`, 214 entries matching the paraphrased set) and are already wired into the report. The **hand spot-check of 20** has not been done — needs a human, or a model call with the page bodies genuinely out of context, not run yet. The 0.62–0.78 operational number quoted in earlier drafts is now the corrected given-hit range 0.69–0.87; still shouldn't headline until this spot-check passes.
- [ ] **0.5 Upstream frontmatter proposal to Cal** — `status`, `supersedes` (uuid), `contradicts`, `depends_on`, `source`, `writer`, `tags`. Draft written (see session transcript); blocked on Cal's contact info or spec-repo link, which isn't in this repo. Needs a human to supply the destination and send it.

## Phase 1 — M1 read path (the tool proper; ~1–2 weeks)

- [ ] **1.1 Repo restructure** (commit). Package `mf/` with a console entry point, `pyproject.toml` installable via `uv tool install .`; harness moves to `eval/` and becomes the regression suite (`eval/run --check` runnable against any build).
- [ ] **1.2 `embedding_text()` as single source of truth.** One function producing title+summary+L1 with model-correct task prefixes, unit-tested, imported by index, search, and (later) dedup. This codifies the M0.5 lesson so it can't be dropped a second time. Same treatment for query preprocessing shared between FTS and the harness baseline (the hyphen/quote sanitization, OR-join, phrase-loss logging).
- [ ] **1.3 Schema + `mf init` + `mf index`.** Tables per plan (`pages, sections, fts, vec, links, claims`); incremental on sha256; refuse-on-stale unless `--stale-ok`; config records model code per spec so indexes never conflate model versions.
- [ ] **1.4 Score gate calibration.** The actual M1 blocker. Per-query floor plus relative-gap heuristic, calibrated on the 30 no-answer queries; add false-answer-rate on the no-answer set as a first-class harness metric. Output contract: `confidence: high|low|none` on every search result set.
- [ ] **1.5 `mf search`.** FTS-first → score gate → dense fallback on low/none. Stubs (uuid, title, summary, status, tokens) + neighbor stubs (typed links, then query-time kNN, then co_read) + `--budget` token cap + `--json`. Superseded pages fold into a `superseded_by` pointer on the winner.
- [ ] **1.6 `mf read`.** `uuid[#section] --tier L1|L2`; logs reads; co_read increment for same-call pairs.
- [ ] **1.7 SKILL.md v0.** Search-before-explore, stub-first reading, when to escalate tiers, the writing conventions.
- [ ] **1.8 Blind vocabulary-mismatch query set.** Authored by a model or person who has never seen the corpus (describe the task, get the question). This takes the ceiling off and is the only way to learn whether the dense fallback ever fires in practice. Re-run full matrix against it (commit before launching).
- [ ] **1.9 Real-agent trial.** N=20 tasks, one agent with mf + skill vs. the same agent with the raw field. Measure tokens-to-answer, stub-end rate operationally, wrong-page reads. This replaces the modeled savings table in PLAN.md §6 with measured numbers.

**Phase 1 exit:** search+read work end-to-end on the eval field; score gate has numbers; savings table is measured, not modeled.

## Phase 2 — M2 write path (~1 week)

- [ ] **2.1 `mf write`** with frontmatter validation and the dedup gate — dense similarity against existing stubs (the vec table's second job), returning near-duplicates with exit code; `--update uuid` / `--force` escape hatches.
- [ ] **2.2 `mf raw add`** appending to non-indexed `raw/`; prefix-dedup for double session-end fires.
- [ ] **2.3 `mf lint`** enforcing plan §5: token budgets, summary-shape heuristic, `## Don't` placement, copied-state patterns (SHAs, counts, relative dates), missing `source`, superseded-but-active, orphans, hash mismatches. `--check` exit code for CI.
- [ ] **2.4 `mf pack` / `unpack`** with sha256; round-trip compatibility test against a spec-plain memoryfield (no extended fields) and Cal's zip layout.

## Phase 3 — M3 hooks and imports (~3 days)

- [ ] **3.1** Claude Code SessionEnd hook → `mf raw add --from-transcript`; CLAUDE.md/AGENTS.md two-line snippet.
- [ ] **3.2** `mf import claude-memory <dir>` (MEMORY.md lines → stubs, topic files → pages) and `mf import wiki <dir>` (index.md entries → summaries, flatten subdirs).
- [ ] **3.3** CI recipe: `mf lint --check` pre-commit; post-commit `mf index`.

## Phase 4 — M4/M5 conditional features

- [ ] **4.1 Reranker eval** — gated on 1.8's blind set. If FTS+gate+dense-fallback holds P@3 there, the reranker is cut, not deferred.
- [ ] **4.2 `mf consolidate --plan`** emitting create/update/supersede JSON from `raw/` with evidence; executed by the host agent via `write`.
- [ ] **4.3 Multi-writer:** `mf claim` (atomic conditional insert), `contested` status, consolidation dedup pass.
- [ ] **4.4 co_read weighting** in neighbor ranking once enough signal accumulates.

## Phase 5 — M6 surfaces and packaging

- [ ] **5.1 MCP server** wrapping search/read/write/raw_add, same JSON contract.
- [ ] **5.2** Packaging polish; Rust port only if install friction is the top user complaint.

---

## Code-review checklist (pending re-upload; also usable as self-audit)

The review I'd run on the harness code, given this project's history:

1. **Single sources of truth.** Is embedding-text construction one function or copy-pasted per baseline? Same for query preprocessing, token counting, and the tokenizer used for budgets — drift here caused the two biggest bugs so far.
2. **Checkpointing.** Does each baseline row write its own result file on completion, or does everything funnel through one summary.json that a kill mid-run corrupts? (This bit once already.)
3. **Determinism and provenance.** Are paraphrase-generation prompts, model versions, and seeds recorded next to the outputs? Can the query sets be regenerated or are they one-of-a-kind artifacts that must never be lost? If the latter, are they committed?
4. **CI math.** Bootstrap implementation — resampling queries (right) vs. resampling hits (wrong); interval on the difference between methods, not just per-method intervals.
5. **Prefix/config hygiene.** Model-specific query/document prefixes in config next to the model name, not hardcoded in a baseline file where the next model swap silently drops them.
6. **Metric conditioning.** Stub-end computed given-hit everywhere, or still mixed in places; no-answer scored as abstention (needs gate) vs. empty-top-k (impossible). **Checked this pass:** was mixed (computed but silently broken, see 0.3), now fixed and consumed by the report.
7. **Hardcoded paths, temp dirs, and whether `eval/` runs from a clean clone.**
8. **Tests.** Anything at all around the FTS query sanitizer and the corpus builder — the two components whose silent failures shaped early conclusions.
9. **Dead code from the flip** — summary-only embedding paths, the unprefixed BGE variant, TF-IDF-labeled-as-dense remnants; delete or mark superseded so the next reader doesn't resurrect a buggy baseline.
10. **README/report drift** — do the docs in the repo still carry the stale "FTS wins" narrative anywhere outside git history?