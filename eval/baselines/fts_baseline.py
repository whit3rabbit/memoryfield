"""FTS5 baseline.

SQLite FTS5 with porter stemming and bm25 ranking. This is the lexical
workhorse; in M1 it stays as one half of the hybrid retrieval.

Index is rebuilt per query session (in-memory DB) for the harness, so we
measure retrieval quality, not indexing cost.
"""
from __future__ import annotations

import sqlite3

from mf.query_prep import fts_query

from ..mf_harness import (
    LookupTrace,
    Page,
    Query,
    full_tokens,
    l1_tokens,
    stub_tokens,
)


def _build_index(corpus: dict[str, Page]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE VIRTUAL TABLE pages USING fts5("
        "uuid UNINDEXED, title, summary, body, "
        "tokenize='porter ascii'"
        ")"
    )
    rows = [
        (page.uuid, page.title, page.summary, page.body) for page in corpus.values()
    ]
    conn.executemany("INSERT INTO pages VALUES (?, ?, ?, ?)", rows)
    return conn


def _rank(conn: sqlite3.Connection, query: Query) -> list[str]:
    fts_q = fts_query(query.text).expr
    if not fts_q:
        return []
    try:
        cur = conn.execute(
            "SELECT uuid, bm25(pages) AS score "
            "FROM pages WHERE pages MATCH ? "
            "ORDER BY score LIMIT 10",
            (fts_q,),
        )
        return [row[0] for row in cur.fetchall()]
    except sqlite3.OperationalError:
        return []


def run(corpus: dict[str, Page], query: Query) -> LookupTrace:
    conn = _build_index(corpus)
    try:
        topk = _rank(conn, query)[:5]
    finally:
        conn.close()
    rank = None
    for i, uuid in enumerate(topk, start=1):
        if uuid in query.answer_uuids:
            rank = i
            break
    if not topk:
        return LookupTrace(
            qid=query.qid,
            baseline="fts",
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
        baseline="fts",
        rank=rank,
        topk_uuids=topk,
        stub_tokens=stub_total,
        l1_tokens=stub_total + l1_tokens(top1),
        full_tokens=stub_total + full_tokens(top1),
        ended_at_stub=query.stub_sufficient and rank == 1,
    )
