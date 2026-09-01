"""Grep baseline.

Plain word-substring search across the corpus. No stemming, no ranking
beyond term frequency. This is the lower bound: what an agent gets with
zero infrastructure.

Token accounting:
  - stub_tokens: tokens for the stub of every hit (worst case agent reads all)
  - l1_tokens: stub + L1 of top-1 hit
  - full_tokens: stub + full body of top-1 hit
"""
from __future__ import annotations

from ..mf_harness import (
    LookupTrace,
    Page,
    Query,
    _tokenize,
    full_tokens,
    l1_tokens,
    stub_tokens,
)


def _rank(corpus: dict[str, Page], query: Query) -> list[str]:
    qterms = set(_tokenize(query.text))
    if not qterms:
        return []
    scored: list[tuple[int, str]] = []
    for uuid, page in corpus.items():
        terms = _tokenize(page.full_text)
        hits = sum(1 for t in qterms if t in terms)
        if hits:
            scored.append((hits, uuid))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [u for _, u in scored]


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
            baseline="grep",
            rank=None,
            topk_uuids=[],
            stub_tokens=0,
            l1_tokens=0,
            full_tokens=0,
            ended_at_stub=False,
        )
    top1 = corpus[topk[0]]
    # Token cost: agent reads stubs of all 5 hits, then L1 of top-1.
    stub_total = sum(stub_tokens(corpus[u]) for u in topk)
    return LookupTrace(
        qid=query.qid,
        baseline="grep",
        rank=rank,
        topk_uuids=topk,
        stub_tokens=stub_total,
        l1_tokens=stub_total + l1_tokens(top1),
        full_tokens=stub_total + full_tokens(top1),
        ended_at_stub=query.stub_sufficient and rank == 1,
    )
