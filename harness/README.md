# M0 — eval harness

> **Nothing else ships until this exists.** — PLAN.md §9

M0 is the eval harness, labeled corpus, and four baselines (grep, FTS,
dense, hybrid). No CLI tool, no `mf index`, no `mf search`. Just the rig
that produces numbers we can trust before we build anything else.

## Why M0 first

The PLAN.md section 6 table ("Expected savings") is *modeled, not measured*.
Every line in section 2's "Architecture" is a bet that the model is right
about token economics. If M0 doesn't prove the model, we should kill the
project before we write a single line of `mf search`.

The harness answers four questions:

1. Does stub-first retrieval hit P@3 ≥ 0.8 on a labeled query set?
2. Does hybrid (BM25 + dense + RRF) beat either alone?
3. What fraction of lookups can end at the stub stage (i.e., is summary
   quality good enough that the agent doesn't need the body)?
4. What's the actual token cost per lookup, end-to-end?

## What's in M0

```
harness/
  README.md              # this file
  corpus/                # generated/curated labeled corpus
    codebase/            # ~75 pages: code-knowledge memory
    papers/              # ~75 pages: research-paper claim memory
  queries/               # labeled query sets (one file per domain)
    codebase/
    papers/
  results/               # raw JSON outputs of baseline runs (gitignored)
  mf_harness.py          # the eval rig (Python, stdlib only)
  baselines/
    grep_baseline.py     # grep-only baseline
    fts_baseline.py      # SQLite FTS5 baseline
    dense_baseline.py    # deterministic "dense" baseline (bag-of-words + tf-idf)
    hybrid_baseline.py   # RRF fusion of FTS + dense
  build_corpus.py        # generates the labeled corpus from seeds
  run_baselines.py       # runs all four baselines, writes results JSON
  report.py              # produces M0_REPORT.md from results JSON
```

The corpus and queries live under `harness/corpus/` and `harness/queries/`
(not the top-level `corpus/` and `queries/` directories, which are placeholders
for the eventual CLI to read from). Top-level `corpus/` and `queries/` will
get populated by M1 and beyond.

## Constraints (from PLAN.md §1)

- **Tokens injected at session start:** target < 200.
- **Tokens per lookup:** target < 1,200, most ending at stub stage.
- **Tool calls per lookup:** target = 2 (search, read).

We measure these in the harness; we don't enforce them yet.

## Baselines (M0 scope only)

Per PLAN.md §6, the harness must compare four configurations:

| Baseline | What it is | Why it's in M0 |
|---|---|---|
| `grep` | Plain substring/word search across the corpus | Lower bound; the "no infrastructure" option |
| `fts` | SQLite FTS5 with porter stemming + bm25 ranking | Lexical retrieval, the workhorse for code recall |
| `dense` | TF-IDF cosine similarity (deterministic stand-in for dense vectors) | No external model dependency; lets us prove the harness works before pulling fastembed |
| `hybrid` | RRF fusion of FTS + dense, top-k from each | The proposed design — does fusion actually help? |

> **Note on `dense`.** In M1 this becomes `nomic-embed-text-v1.5` via
> fastembed. In M0 we use TF-IDF because (a) it needs no model download and
> (b) it's a useful control — if TF-IDF already hits P@3 ≥ 0.8, the embedder
> buys less than the plan assumes.

## Metrics

The harness reports, per baseline per domain:

- **P@3** — fraction of queries where a relevant page appears in the top 3
  stubs.
- **R@5** — fraction of relevant pages (per query) retrieved in the top 5.
- **Stub-end rate** — fraction of queries where the stub summary alone (with
  no body read) would have given the agent enough to answer. Judged by
  comparing the stub summary to the labeled `answer_uuid`'s summary.
- **Tokens per lookup (median, p95)** — for a stub-only lookup and for a
  stub + L1 lookup, computed from the actual rendered output.
- **MRR** — mean reciprocal rank of the first relevant page.

The full numbers land in `M0_REPORT.md` at the end of M0.

## How to run

```bash
# from the repo root
python3 harness/build_corpus.py        # writes harness/corpus/{codebase,papers}/
python3 harness/run_baselines.py       # writes harness/results/*.json
python3 harness/report.py              # writes M0_REPORT.md
```

The harness uses Python stdlib only. No `pip install` for M0.

## What M0 is *not*

- Not a CLI. There's no `mf` binary yet.
- Not a real embedder. Dense baseline is TF-IDF.
- Not networked. No model downloads.
- Not asserting performance. Numbers are honest about being small-N.

If M0 numbers look bad, we change the plan. We do not retrofit the plan
to explain bad numbers away.

## Exit criteria for M0

M0 is "done" when:

- [ ] ~150 pages of labeled corpus exist (≥ 75 per domain).
- [ ] ≥ 60 labeled queries exist (≥ 30 per domain), each with at least one
      `answer_uuid` and a `stub_sufficient: bool` label.
- [ ] All four baselines run end-to-end on both domains.
- [ ] `M0_REPORT.md` reports P@3, R@5, MRR, stub-end rate, and tokens/lookup
      for every (baseline, domain) pair.
- [ ] Report explicitly states whether each baseline met, exceeded, or fell
      short of the design targets in PLAN.md §1.
