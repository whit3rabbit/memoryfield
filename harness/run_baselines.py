"""Run all M0 baselines against both domains.

For each (baseline, domain) pair:
  - load the corpus and queries
  - run the baseline on each query
  - compute P@3, P@5, R@5, MRR, stub-end rate, token counts
  - write a JSON results file under harness/results/

Usage:
    python3 harness/run_baselines.py
    python3 harness/run_baselines.py --baseline fts --domain code  # filter
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

# Make sure we have the deps the dense baselines need. We deliberately
# don't `pip install` at import time; instead the runner expects to be
# invoked from an environment where fastembed is already available
# (e.g. `~/.hermes/hermes-agent/venv/bin/python3 -m harness.run_baselines`).
try:
    import fastembed  # noqa: F401
except ImportError:
    sys.stderr.write(
        "fastembed not found in current Python environment.\n"
        "The runner needs the hermes-agent venv (or any venv with fastembed installed).\n"
        "Try: ~/.hermes/hermes-agent/venv/bin/python3 -m harness.run_baselines\n"
    )
    raise

from harness.mf_harness import (
    BaselineMetrics,
    LookupTrace,
    Query,
    compute_metrics,
    load_corpus,
    load_queries,
    percentile,
)

from harness.baselines import (
    dense_baseline,
    dense_real_baseline,
    fts_baseline,
    grep_baseline,
    hybrid_baseline,
)

ROOT = Path(__file__).parent
CORPUS_DIR = ROOT / "corpus"
QUERIES_DIR = ROOT / "queries"
RESULTS_DIR = ROOT / "results"

BASELINES = {
    "grep": grep_baseline.run,
    "fts": fts_baseline.run,
    "dense_tfidf": dense_baseline.run,
    "dense_nomic": dense_real_baseline.run_nomic,
    "dense_bge": dense_real_baseline.run_bge,
    "hybrid": hybrid_baseline.run,
}

DOMAINS = {
    "codebase": ("codebase", "code"),
    "papers": ("papers", "papers"),
}


def run_one(baseline_name: str, domain_name: str) -> BaselineMetrics:
    corpus_path, query_domain = DOMAINS[domain_name]
    corpus = load_corpus(CORPUS_DIR / corpus_path)
    queries = load_queries(
        QUERIES_DIR / corpus_path / "queries.jsonl", query_domain
    )

    print(f"  {baseline_name:>8} on {domain_name:>8}: "
          f"corpus={len(corpus):>3}, queries={len(queries):>3}")

    fn = BASELINES[baseline_name]
    traces: list[LookupTrace] = []
    t0 = time.perf_counter()
    for q in queries:
        trace = fn(corpus, q)
        traces.append(trace)
    elapsed = time.perf_counter() - t0

    # Compute R@5 properly now that we have access to query.answer_uuids.
    # Also compute "no-answer correctness": for queries where answer_uuids is
    # empty, we count a hit if no answer page (by qid, since answer_uuids=[]
    # means no expected) appears in top-k.
    r_at_5_sum = 0.0
    r_at_5_n = 0
    p_at_3 = 0
    p_at_5 = 0
    mrr_sum = 0.0
    stub_ends = 0
    stub_tokens = []
    l1_tokens = []
    full_tokens = []
    no_answer_correct = 0
    no_answer_n = 0
    per_query = []

    for q, t in zip(queries, traces):
        is_no_answer = (len(q.answer_uuids) == 0)

        if is_no_answer:
            # No-answer query: success means NO page was retrieved at all
            # (empty top-k). Anything in top-k is a false positive — there
            # is no answer for this query by definition.
            if not t.topk_uuids:
                no_answer_correct += 1
            no_answer_n += 1
        else:
            if t.rank is not None:
                mrr_sum += 1.0 / t.rank
                if t.rank <= 3:
                    p_at_3 += 1
                if t.rank <= 5:
                    p_at_5 += 1
            # R@5: fraction of labeled answer uuids in top-5
            if t.topk_uuids:
                hits = sum(1 for u in q.answer_uuids if u in t.topk_uuids)
                r_at_5_sum += hits / max(1, len(q.answer_uuids))
            else:
                r_at_5_sum += 0.0
            r_at_5_n += 1

        if t.ended_at_stub:
            stub_ends += 1
        stub_tokens.append(t.stub_tokens)
        l1_tokens.append(t.l1_tokens)
        full_tokens.append(t.full_tokens)
        per_query.append({
            "qid": q.qid,
            "text": q.text,
            "answer_uuids": q.answer_uuids,
            "stub_sufficient": q.stub_sufficient,
            "query_kind": q.query_kind,
            "query_type": q.query_type,
            "rank": t.rank,
            "topk": t.topk_uuids,
            "stub_tokens": t.stub_tokens,
            "l1_tokens": t.l1_tokens,
            "full_tokens": t.full_tokens,
            "ended_at_stub": t.ended_at_stub,
            "is_no_answer": is_no_answer,
        })

    n = len(traces)
    metrics = BaselineMetrics(
        baseline=baseline_name,
        domain=domain_name,
        n_queries=n,
        p_at_3=p_at_3 / r_at_5_n if r_at_5_n else 0,
        p_at_5=p_at_5 / r_at_5_n if r_at_5_n else 0,
        r_at_5=r_at_5_sum / r_at_5_n if r_at_5_n else 0,
        mrr=mrr_sum / r_at_5_n if r_at_5_n else 0,
        stub_end_rate=stub_ends / n if n else 0,
        tokens_stub_median=statistics.median(stub_tokens) if stub_tokens else 0,
        tokens_stub_p95=percentile(stub_tokens, 95) if stub_tokens else 0,
        tokens_l1_median=statistics.median(l1_tokens) if l1_tokens else 0,
        tokens_full_median=statistics.median(full_tokens) if full_tokens else 0,
        details_path=RESULTS_DIR / f"{baseline_name}_{domain_name}.json",
    )

    # Add no-answer correctness to metrics by attaching to details.
    no_answer_rate = (no_answer_correct / no_answer_n) if no_answer_n else 0.0

    # Write detailed results.
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    details = {
        "baseline": baseline_name,
        "domain": domain_name,
        "n_pages": len(corpus),
        "n_queries": n,
        "n_no_answer": no_answer_n,
        "no_answer_correct": no_answer_correct,
        "no_answer_rate": no_answer_rate,
        "elapsed_seconds": round(elapsed, 4),
        "metrics": metrics.as_dict(),
        "per_query": per_query,
    }
    metrics.details_path.write_text(json.dumps(details, indent=2))
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", choices=list(BASELINES), default=None)
    parser.add_argument("--domain", choices=list(DOMAINS), default=None)
    args = parser.parse_args()

    baselines = [args.baseline] if args.baseline else list(BASELINES)
    domains = [args.domain] if args.domain else list(DOMAINS)

    print(f"Running M0 baselines: {baselines} x {domains}")
    all_metrics: list[BaselineMetrics] = []
    for b in baselines:
        for d in domains:
            m = run_one(b, d)
            all_metrics.append(m)
            print(
                f"    P@3={m.p_at_3:.3f}  R@5={m.r_at_5:.3f}  "
                f"MRR={m.mrr:.3f}  stub_end={m.stub_end_rate:.3f}  "
                f"tokens(stub)={m.tokens_stub_median:.0f}/{m.tokens_stub_p95:.0f}"
            )

    # Summary
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps([m.as_dict() for m in all_metrics], indent=2))
    print(f"\nSummary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
