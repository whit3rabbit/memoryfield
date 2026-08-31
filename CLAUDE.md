# CLAUDE.md

Memoryfield eval harness — context for the next agent (human or model).

## What this repo is

Eval harness for the `mf` memoryfield tool described in `PLAN.md`.
**No tool implementation lives here yet.** M0 and M0.5 are eval + corpus
only. M1 (`init` / `index` / `search` / `read` / `write`) is the first code
that ships.

## Critical context

Two commits so far. The first (`0004448`) was the initial M0 + M0.5
harness and is **stale** — see "The headline numbers flipped" below.
The second commit is uncommitted-on-disk: bug fixes that materially changed
the eval picture. **Read the disk before reading the prior summary.**

### The headline numbers flipped mid-development

Initial commit reported "FTS wins on every axis" (FTS P@3 0.95+ averaged;
nomic papers 0.717; bge codebase 0.908). Two bugs in `dense_real_baseline.py`
caused that picture:

1. **Embedding text was summary-only**, dropping the title and L1 body
   even though the docstring said "title + summary + L1."
   Fix in `harness/baselines/dense_real_baseline.py:62-78`. After fix,
   nomic papers P@3 went from 0.717 → **0.988**, bge codebase from
   0.908 → **0.989**.
2. **BGE query prefix was missing.** BGE-en-v1.5 expects
   `"Represent this sentence for searching relevant passages: "` on
   queries; fastembed does not add it automatically.
   Fix in `harness/baselines/dense_real_baseline.py:88-101`.

After both fixes, dense dominates on most axes (full numbers below).
**The original commit's narrative is no longer accurate; trust the on-disk
results, not the narrative in the commit message.**

## Current state on disk

**Committed (`0004448`):** M0 + M0.5 harness, corpus, queries, subagent
artifacts, M0_REPORT.md, initial dense baselines with the bugs above.

**Uncommitted (run `git status` for the full list):**
- Bug fixes to `harness/baselines/dense_real_baseline.py`
- `mf_harness.py`: added `bootstrap_ci()` for 95% CIs on P@3, R@5
- `run_baselines.py`: CI computation, `stub_end_given_hit_rate` metric,
  honest comment on no-answer metric (top-k always returns k — wrong test)
- `axis_breakdown.py`: per-baseline per-axis tables including
  `no-ans empty` rate
- `report.py`: substantive_findings() + corrected headlines
- `STATUS.md`: eval-state notes
- `harness/results/*.json`: re-run results with bug fixes
  - grep, fts, dense_tfidf, dense_nomic (both domains): committed
    versions are stale; uncommitted versions are current
  - dense_bge: codebase done, papers pending
  - hybrid: codebase done, papers pending
- `M0.5_REPORT.md`: not yet generated

## Headline numbers (current on disk, after bug fixes)

Per-domain P@3, real-answer queries only:

| Baseline     | Codebase | Papers  |
|--------------|----------|---------|
| grep         | 0.776    | 0.878   |
| fts          | 0.943    | 0.961   |
| dense_tfidf  | 0.885    | 0.902   |
| dense_nomic  | **0.966**| **0.988** |
| dense_bge    | **0.989**| pending |
| hybrid       | **0.977**| pending |

**Direction changed:** dense now wins on real-answer recall. FTS remains
strong and has the only "no-answer empty" abstention behavior (returns
empty top-k for ~12% of no-answer queries). Hybrid codebase (FTS+nomic RRF)
beats either alone.

## Gotchas and lessons learned

These are the things that bit us, organized by where they'll bite next.

### Eval harness gotchas

1. **Embedding bugs don't show up at the corpus level — only at retrieval.**
   A 1-character bug in the embedder input string silently degrades
   dense recall by 30 points on a specific domain. Always sanity-check
   a single embedding's text content before trusting aggregate numbers.

2. **fastembed does not add the BGE query prefix for you.** It adds the
   nomic prefix implicitly via task-specific inference. BGE is the same
   kind of model (asymmetric prefix) but fastembed treats it as symmetric.
   If you swap models, re-check the prefix convention.

3. **fastembed TextEmbedding is not thread-safe across two instantiations.**
   Loading both nomic and bge in the same process (which the hybrid
   baseline does today) can deadlock with `recursive_mutex lock failed:
   Invalid argument`. Workaround: keep models separate in time, or run
   hybrid as two sequential calls (FTS first, dense second) instead of
   fusing live. The current hybrid does FTS+nomic simultaneously and
   occasionally crashes — this is why the second dense_bge_papers run
   crashed mid-flight.

4. **TF-IDF is not dense.** Don't confuse them. The first commit's
   "dense baseline" was TF-IDF and its "FTS > dense" finding was
   nonsense for the same reason a TF-IDF vs FTS comparison can't tell
   you anything about dense. If you see `dense_baseline.py` in the
   harness, that file is the control, not the real thing.

5. **Top-k always returns k.** The first version of the no-answer
   metric tracked whether the retriever returned an empty top-k; this
   is a meaningless test because no real retriever abstains. The
   honest framing is: "no baseline has an abstention mechanism, so the
   no-answer metric is undefined until M1 builds one." The 30 no-answer
   queries are still useful — they're the calibration set for the
   future abstention feature.

6. **De-biased stub labels are more permissive than original author
   labels.** Original author used an operational bar ("agent wouldn't
   need body"); de-bias used an informational bar ("stub has the
   answer"). 99.1% vs 67-82%. Both are valid; report both, lead with the
   operational one (the one PLAN.md §6's token-savings model depends on).

7. **The query set shares an authoring process with the corpus.**
   Pages were written, then queries were written to match them, then
   paraphrases were written from the queries. Single-vocabulary
   throughout. This is the best case lexical search will ever see.
   "FTS wins" finding was conditional on this — promote that caveat to
   the headline of any report that claims FTS-first.

### Process gotchas

8. **Subagent outputs are not regeneratable identically.** The paraphrases,
   topical/entity tags, and stub-end de-bias judgments all came from
   background subagents with non-zero sampling temperature. If you
   regenerate, the labels will differ. The on-disk files are the
   canonical version; backup before regenerating.

9. **`summary.json` gets overwritten on every per-baseline run.** The
   runner writes summary.json after each baseline, so a single mid-run
   failure leaves only the most recent baseline in summary. To reconstruct
   the full summary, read all `results/*.json` and aggregate — there is a
   helper in `run_baselines.py` you can repurpose.

10. **Don't run the full baseline suite in foreground.** Six baselines ×
    two domains × 191–267 queries × 1–5 sec per query = ~15 minutes for
    the fast baselines, ~45 minutes for BGE+papers. Always use
    `background=true` and `process(action='wait')`.

11. **The first commit is partially-stale narrative.** When reviewing
    M0_REPORT.md or the commit message, cross-check against on-disk
    results in `harness/results/*.json`. Numbers in the commit may not
    match the disk.

### Plan-design gotchas (for M1 implementation)

12. **The plan's "hybrid" needs re-design.** Symmetric RRF at equal
    weights degrades the strong signal. Three options for M1:
    (a) sequence, don't fuse — FTS first, dense as fallback only when
    FTS term coverage is low;
    (b) asymmetric RRF — weight FTS higher (e.g. 2:1) since lexical
    is the workhorse;
    (c) keep hybrid for the codebase, drop it for papers where dense
    alone wins.

13. **The vec table is load-bearing for three features, not one.** Don't
    let "dense lost on ranking" quietly delete it. The plan requires
    the vec table for: (a) kNN neighbor stubs, (b) write-time dedup of
    paraphrased near-duplicates, (c) fallback when FTS returns nothing.
    Only ranking-#1 was contested; the other three need dense.

14. **The plan needs a no-answer confidence signal before M1 ships.**
    Currently the plan returns top-k unconditionally. Add a per-query
    floor + relative-gap heuristic on retrieval scores, and a
    `confidence: low` flag in the search response. The 30 no-answer
    queries are the calibration set.

15. **`lint` is load-bearing infrastructure, not nice-to-have.**
    The "FTS wins" finding only holds because page summaries are
    information-dense (commands, formulas, defaults). That density
    comes from writing discipline. If `lint` (PLAN.md §5) isn't
    enforced, retrieval quality drifts toward the dense-only
    distribution — which would actually *change* the M1 design
    verdict toward hybrid-first.

## Roadmap

See [PLAN.md](PLAN.md) §9. Milestone status:

- [x] **M0** — eval harness with labeled corpus and 6 baselines.
- [x] **M0.5** — real dense baselines (nomic, bge), 458-query set with
  blind paraphrases + no-answer queries, topical/entity tagging, de-biased
  stub-end labels. **M0.5 headline numbers flipped after bug fixes** —
  do not trust the original commit's narrative; see "Critical context"
  above.
- [ ] **M1 — read path.** `init`, `index`, `search`, `read`. NOT
  STARTED. This is the next milestone. The eval numbers from M0.5
  support a FTS-primary architecture with confidence-gated abstention
  and dense as fallback + neighbors + dedup.
- [ ] **M2 — write path.** `write` (with dedup gate), `raw add`, `lint`,
  `pack`/`unpack`. The `lint` rules from PLAN.md §5 are now load-bearing,
  not optional.
- [ ] **M3 — hooks and imports.** Claude Code SessionEnd hook, AGENTS.md
  integration, importers.
- [ ] **M4 — reranker and eval gate.** Optional cross-encoder reranker
  if eval P@3 < 0.8 — current eval puts us well above that.
- [ ] **M5 — consolidation and multi-writer.** `consolidate --plan`,
  `claims` table for atomic creates, `contested` status for human
  resolution.
- [ ] **M6 — MCP server, then packaging.** Rust port only if install
  friction is the top complaint.

### Open debt before M1 ships

- Run dense_bge_papers and hybrid_papers to complete the table.
- Generate M0.5_REPORT.md with the corrected headline (dense wins on
  most axes; FTS keeps the abstention edge).
- Commit the bug fixes as a second commit with the picture-flip story.
- Decide hybrid design: sequence vs asymmetric RRF.
- Add confidence signal to search API contract.
