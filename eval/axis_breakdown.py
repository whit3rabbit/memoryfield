"""Per-axis breakdown of M0.5 results.

Reads the per-baseline JSON results and buckets queries by:
  - query_kind: lexical / paraphrased / no_answer_*
  - query_type: entity / topical
  - domain: code / papers

Outputs a markdown table per baseline per axis.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"


def load_all() -> dict[tuple[str, str], list[dict]]:
    """(baseline, domain) -> list of per-query result dicts."""
    out = {}
    for p in RESULTS_DIR.glob("*_codebase.json"):
        baseline = p.stem.replace("_codebase", "")
        data = json.loads(p.read_text())
        out[(baseline, "codebase")] = data["per_query"]
    for p in RESULTS_DIR.glob("*_papers.json"):
        baseline = p.stem.replace("_papers", "")
        data = json.loads(p.read_text())
        out[(baseline, "papers")] = data["per_query"]
    return out


def bucketize(records: list[dict]) -> dict[str, list[dict]]:
    """Partition records into analysis buckets."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        kind = r.get("query_kind", "lexical")
        qtype = r.get("query_type", "entity")
        out["all"].append(r)
        if kind == "lexical":
            out["lexical"].append(r)
        elif kind == "paraphrased":
            out["paraphrased"].append(r)
        elif kind.startswith("no_answer"):
            out["no_answer"].append(r)
        if qtype == "topical":
            out["topical"].append(r)
        elif qtype == "entity":
            out["entity"].append(r)
        # intersections
        if kind == "paraphrased":
            out["paraphrased_topical" if qtype == "topical" else "paraphrased_entity"].append(r)
        if kind == "lexical":
            out["lexical_topical" if qtype == "topical" else "lexical_entity"].append(r)
    return out


def metrics_for_bucket(records: list[dict]) -> dict[str, float]:
    """Compute per-bucket metrics. Skip no-answer queries for P/R/MRR."""
    real = [r for r in records if not r["is_no_answer"]]
    noans = [r for r in records if r["is_no_answer"]]
    n = len(records)
    n_real = len(real)
    n_noans = len(noans)
    if n_real:
        p_at_3 = sum(1 for r in real if r["rank"] is not None and r["rank"] <= 3) / n_real
        p_at_5 = sum(1 for r in real if r["rank"] is not None and r["rank"] <= 5) / n_real
        r_at_5_sum = 0.0
        for r in real:
            expected = r.get("answer_uuids", [])
            if expected and r["topk"]:
                hits = sum(1 for u in expected if u in r["topk"])
                r_at_5_sum += hits / len(expected)
        r_at_5 = r_at_5_sum / n_real if n_real else 0.0
        mrr = sum((1.0 / r["rank"]) if r["rank"] else 0 for r in real) / n_real if n_real else 0
    else:
        p_at_3 = p_at_5 = r_at_5 = mrr = 0.0
    noans_correct = sum(1 for r in noans if not r["topk"])
    return {
        "n": n,
        "n_real": n_real,
        "n_noans": n_noans,
        "p_at_3": p_at_3,
        "p_at_5": p_at_5,
        "r_at_5": r_at_5,
        "mrr": mrr,
        "noans_zero_rate": noans_correct / n_noans if n_noans else 0,
    }


def render_breakdown_table(by_baseline_domain: dict) -> str:
    """Render per-baseline x per-axis tables."""
    # Group by baseline
    by_baseline: dict[str, dict[str, list[dict]]] = {}
    for (b, d), records in by_baseline_domain.items():
        by_baseline.setdefault(b, {})[d] = records

    out = []
    BASELINES_OF_INTEREST = ["grep", "fts", "dense_nomic", "dense_bge", "dense_tfidf", "hybrid"]
    AXES = ["all", "lexical", "paraphrased", "no_answer", "entity", "topical",
            "lexical_entity", "paraphrased_entity",
            "lexical_topical", "paraphrased_topical"]
    for baseline in BASELINES_OF_INTEREST:
        if baseline not in by_baseline:
            continue
        out.append(f"### `{baseline}`")
        out.append("")
        out.append(
            "| Axis | Domain | N | N(no-ans) | P@3 | P@5 | R@5 | MRR | no-ans zero-rate |"
        )
        out.append("|---|---|---|---|---|---|---|---|---|")
        # Combine both domains for headline, then per-domain
        for domain in ["codebase", "papers"]:
            d_key = "codebase" if domain == "codebase" else "papers"
            if d_key not in by_baseline[baseline]:
                continue
            records = by_baseline[baseline][d_key]
            buckets = bucketize(records)
            for axis in AXES:
                recs = buckets.get(axis, [])
                if not recs:
                    continue
                m = metrics_for_bucket(recs)
                out.append(
                    f"| {axis} | {domain} | {m['n']} | {m['n_noans']} | "
                    f"{m['p_at_3']:.3f} | {m['p_at_5']:.3f} | {m['r_at_5']:.3f} | "
                    f"{m['mrr']:.3f} | {m['noans_zero_rate']:.3f} |"
                )
        out.append("")
    return "\n".join(out)


def main() -> int:
    data = load_all()
    md = render_breakdown_table(data)
    out_path = ROOT / "axis_breakdown.md"
    out_path.write_text(md + "\n")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
