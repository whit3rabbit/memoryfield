"""Hybrid baseline: RRF fusion of FTS5 + dense (TF-IDF).

Reciprocal Rank Fusion: each retriever contributes a score of
`1 / (k + rank)` for each result; we sum across retrievers and re-sort.
`k=60` is the standard constant from the original Cormack et al. paper and
the value qmd and most modern stacks default to.

This is the proposed design from PLAN.md §2 ("Retrieve"). If it doesn't
beat either baseline alone, the architecture needs rethinking.
"""
from __future__ import annotations

import sqlite3

from ..mf_harness import (
    LookupTrace,
    Page,
    Query,
    full_tokens,
    l1_tokens,
    stub_tokens,
)
from . import dense_real_baseline, fts_baseline

RRF_K = 60


def _rank(corpus: dict[str, Page], query: Query) -> list[str]:
    # FTS5
    fts_conn = sqlite3.connect(":memory:")
    try:
        fts_conn.execute(
            "CREATE VIRTUAL TABLE pages USING fts5("
            "uuid UNINDEXED, title, summary, body, tokenize='porter ascii'"
            ")"
        )
        fts_conn.executemany(
            "INSERT INTO pages VALUES (?, ?, ?, ?)",
            [(p.uuid, p.title, p.summary, p.body) for p in corpus.values()],
        )
        fts_q = fts_baseline._query_to_fts(query.text)
        if fts_q:
            cur = fts_conn.execute(
                "SELECT uuid FROM pages WHERE pages MATCH ? ORDER BY bm25(pages) LIMIT 20",
                (fts_q,),
            )
            fts_ranked = [row[0] for row in cur.fetchall()]
        else:
            fts_ranked = []
    except sqlite3.OperationalError:
        fts_ranked = []
    finally:
        fts_conn.close()

    # Dense (real, nomic) for the asymmetric fusion. We use the same
    # dense_real_baseline code path so the embedder and prefix handling
    # are identical to dense_nomic.
    from . import dense_real_baseline
    dc = dense_real_baseline.DenseIndex(
        "nomic-ai/nomic-embed-text-v1.5", "nomic"
    )
    dc.add_corpus(corpus)
    dense_ranked = [u for u, _ in dc.query(query.text, k=20)]

    # RRF fusion
    fused: dict[str, float] = {}
    for rank, uuid in enumerate(fts_ranked, start=1):
        fused[uuid] = fused.get(uuid, 0.0) + 1.0 / (RRF_K + rank)
    for rank, uuid in enumerate(dense_ranked, start=1):
        fused[uuid] = fused.get(uuid, 0.0) + 1.0 / (RRF_K + rank)

    sorted_uuids = sorted(fused.items(), key=lambda x: (-x[1], x[0]))
    return [u for u, _ in sorted_uuids][:10]


def run(corpus: dict[str, Page], query: Query) -> LookupTrace:
    topk = _rank(corpus, query)[:5]
    rank = None
    for i, uuid in enumerate(topk, start=1):
        if uuid in query.answer_uuids:
            rank = i
            break
    if not topk:
        return LookupTrace(
            qid=query.qid,
            baseline="hybrid",
            rank=None,
            topk_uuids=[],
            stub_tokens=0,
            l1_tokens=0,
            full_tokens=0,
            ended_at_stub=False,
        )
    top1 = corpus[topk[0]]
    stub_total = sum(stub_tokens(corpus[u]) for u in topk)
    return LookupTrace(
        qid=query.qid,
        baseline="hybrid",
        rank=rank,
        topk_uuids=topk,
        stub_tokens=stub_total,
        l1_tokens=stub_total + l1_tokens(top1),
        full_tokens=stub_total + full_tokens(top1),
        ended_at_stub=query.stub_sufficient and rank == 1,
    )
