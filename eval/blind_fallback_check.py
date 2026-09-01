"""ROADMAP.md 1.8: does `mf/search.py`'s dense fallback ever fire?

Superseded as a question by ROADMAP.md 2.6: `mf search` now ranks by
dense on every query, so "FTS empty -> dense" is no longer a fallback
branch. Kept runnable as the 1.8 record; `eval/calibrate_confidence_blind.py`
is the current measurement of the pipeline.

The 6-baseline eval matrix (`run_baselines.py`) can't answer this on its
own: every baseline's top-k always returns k (CLAUDE.md gotcha 6), so
none of them ever have an "FTS found nothing" case to fall back from.
Only `mf/search.py`'s own `search()` has that branch -- it uses dense's
top-k as the *result set* only when FTS's ranked list is empty (empty
MATCH expression, or zero hits).

This script builds a real field from each domain's corpus, runs the
real `mf search` pipeline (real sqlite-vec + fastembed, not mocked)
against both the blind (eval/queries/<domain>/queries_blind.jsonl) and
original (eval/queries/<domain>/queries.jsonl) query sets, and reports
how often the fallback actually triggers on each -- the comparison
1.8 exists to make possible.

Usage: uv run python3 -m eval.blind_fallback_check
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from sqlite3 import Connection
from typing import Any

from eval.mf_harness import load_queries
from mf import db, indexer
from mf import search as search_mod
from mf.embedding import query_text
from mf.search import _fts_search, search

ROOT = Path(__file__).parent
CORPUS_DIR = ROOT / "corpus"
QUERIES_DIR = ROOT / "queries"

DOMAINS = {
    "codebase": "code",
    "papers": "papers",
}

# search()'s real _embed_query() reloads fastembed's TextEmbedding from
# scratch on every single call -- fine for one-shot CLI invocations
# (which is all it's ever used for otherwise), ruinous for ~500 calls in
# one process here. Cache by model_name; the embeddings themselves are
# unchanged, real fastembed output, not mocked.
_MODEL_CACHE: dict[str, Any] = {}


def _cached_embed_query(query: str, model_code: str) -> list[float]:
    model_kind, model_name = "nomic", "nomic-ai/nomic-embed-text-v1.5"
    if model_name not in _MODEL_CACHE:
        from fastembed import TextEmbedding
        _MODEL_CACHE[model_name] = TextEmbedding(model_name=model_name)
    model = _MODEL_CACHE[model_name]
    vec = next(iter(model.embed([query_text(query, model_kind)])))
    return [float(v) for v in vec]


def _build_field(corpus_subdir: str) -> tuple[Path, Connection]:
    tmp = Path(tempfile.mkdtemp(prefix=f"mf-fallback-{corpus_subdir}-"))
    for p in (CORPUS_DIR / corpus_subdir).glob("*.md"):
        (tmp / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    db.init_field(tmp)
    conn = db.open_field(tmp)
    indexer.index_field(tmp, conn)
    return tmp, conn


def _measure(conn: Connection, queries: list) -> dict:
    fts_empty = 0
    confidence_counts = {"high": 0, "low": 0, "none": 0}
    top1_correct = 0
    n_real_answer = 0

    for q in queries:
        fts_ranked, _term_count = _fts_search(conn, q.text, limit=5)
        if not fts_ranked:
            fts_empty += 1

        result = search(conn, q.text, limit=5)
        confidence_counts[result.confidence] += 1

        if q.answer_uuids:
            n_real_answer += 1
            if result.results and result.results[0].uuid in q.answer_uuids:
                top1_correct += 1

    n = len(queries)
    return {
        "n": n,
        "dense_fallback_rate": fts_empty / n if n else 0.0,
        "confidence": confidence_counts,
        "top1_accuracy_real_answer": (
            top1_correct / n_real_answer if n_real_answer else None
        ),
        "n_real_answer": n_real_answer,
    }


def main() -> int:
    search_mod._embed_query = _cached_embed_query
    print(f"{'domain':<10} {'set':<10} {'n':>4} {'fallback%':>10} "
          f"{'high':>5} {'low':>5} {'none':>5} {'top1_acc':>9}")
    for corpus_subdir, query_domain in DOMAINS.items():
        tmp, conn = _build_field(corpus_subdir)
        try:
            for label, filename in (
                ("original", "queries.jsonl"),
                ("blind", "queries_blind.jsonl"),
            ):
                queries = load_queries(
                    QUERIES_DIR / corpus_subdir / filename, query_domain
                )
                m = _measure(conn, queries)
                c = m["confidence"]
                acc = m["top1_accuracy_real_answer"]
                acc_s = f"{acc:.3f}" if acc is not None else "n/a"
                print(
                    f"{corpus_subdir:<10} {label:<10} {m['n']:>4} "
                    f"{m['dense_fallback_rate']*100:>9.1f}% "
                    f"{c['high']:>5} {c['low']:>5} {c['none']:>5} {acc_s:>9}"
                )
        finally:
            conn.close()
            shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
