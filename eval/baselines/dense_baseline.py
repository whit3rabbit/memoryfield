"""Dense baseline (TF-IDF stand-in).

In M1 this becomes `nomic-embed-text-v1.5` via fastembed. In M0 we use
TF-IDF because (a) it needs no model download, and (b) if TF-IDF already
hits reasonable P@3, the dense embedder buys less than the plan assumes.

This is *the control experiment*. If dense doesn't beat FTS, the design
in PLAN.md §2 is wrong about why dense helps.
"""
from __future__ import annotations

from ..mf_harness import (
    LookupTrace,
    Page,
    Query,
    _tokenize,
    build_tfidf,
    cosine_sparse,
    full_tokens,
    l1_tokens,
    stub_tokens,
    tfidf_vector,
)


def _rank(corpus: dict[str, Page], query: Query) -> list[str]:
    docs, idf, _df = build_tfidf(corpus.values())
    page_uuids = list(corpus.keys())
    doc_vectors = [tfidf_vector(terms, idf) for terms in docs]
    qvec = tfidf_vector(_tokenize(query.text), idf)
    scored = [
        (cosine_sparse(qvec, dv), uuid)
        for dv, uuid in zip(doc_vectors, page_uuids, strict=True)
    ]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [uuid for score, uuid in scored if score > 0][:10]


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
            baseline="dense",
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
        baseline="dense",
        rank=rank,
        topk_uuids=topk,
        stub_tokens=stub_total,
        l1_tokens=stub_total + l1_tokens(top1),
        full_tokens=stub_total + full_tokens(top1),
        ended_at_stub=query.stub_sufficient and rank == 1,
    )
