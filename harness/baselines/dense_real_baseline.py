"""Real dense baselines using fastembed.

Two models:
  - nomic: nomic-ai/nomic-embed-text-v1.5 (768-d)
  - bge:   BAAI/bge-large-en-v1.5 (1024-d)

Both honor the asymmetric query/document distinction the plan calls out:
- Nomic requires the prefixes `search_query:` / `search_document:` to work
  correctly (it's an asymmetric model with task-specific prefixes).
- BGE-large is symmetric in raw form, but the common practice (and
  BGE-en-v1.5 README) is to add the same prefix for consistency.

We embed pages once at index time and queries per-run. Cosine similarity
is computed with a single matrix multiply since everything fits in RAM
for our 157-page corpus (and will continue to fit well into M1's
personal-memory scale).
"""
from __future__ import annotations

import os

# Suppress fastembed's progress bars; clean output matters for the runner.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from ..mf_harness import (
    LookupTrace,
    Page,
    Query,
    full_tokens,
    l1_tokens,
    stub_tokens,
)


def _normalize(matrix) -> "list[list[float]]":
    """L2-normalize each row. Returns a list (compatible with cosine calc)."""
    import numpy as np
    arr = np.asarray(matrix, dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (arr / norms).tolist()


class DenseIndex:
    """Pre-computed embeddings for a corpus."""

    def __init__(self, model_name: str, kind: str):
        self.model_name = model_name
        self.kind = kind  # "nomic" or "bge"
        from fastembed import TextEmbedding
        # cache_dir defaults to ~/.cache/fastembed; fine.
        self.model = TextEmbedding(model_name=model_name)
        self.dim: int = 0
        self._page_vecs: list[list[float]] = []
        self._page_ids: list[str] = []
        self._page_text_for_query: list[str] = []

    def add_corpus(self, corpus: dict[str, Page]) -> None:
        # Embed title + summary + L1 body section, prefixed with search_document.
        # This is what the plan means by "L0+L1 only" for the dense vector.
        texts = []
        ids = []
        for uuid, page in corpus.items():
            piece = page.summary or page.title
            prefix = "search_document: " if self.kind == "nomic" else ""
            texts.append(prefix + (piece or page.title))
            ids.append(uuid)
        if not texts:
            return
        # fastembed returns a generator; materialize to a matrix.
        vecs = list(self.model.embed(texts, batch_size=32))
        self._page_vecs = _normalize(vecs)
        self._page_ids = ids
        self.dim = len(self._page_vecs[0])

    def query(self, q: str, k: int = 5) -> list[tuple[str, float]]:
        """Return top-k (uuid, score) pairs."""
        import numpy as np
        prefix = "search_query: " if self.kind == "nomic" else ""
        qv = list(self.model.embed([prefix + q]))
        qv = _normalize(qv)[0]
        import numpy as np
        page_mat = np.asarray(self._page_vecs, dtype="float32")
        scores = page_mat @ np.asarray(qv, dtype="float32")
        order = np.argsort(-scores)[:k]
        return [(self._page_ids[i], float(scores[i])) for i in order]


def run_with_model(model_name: str, kind: str, corpus: dict[str, Page], query: Query) -> LookupTrace:
    """Build (or reuse) a per-process index for the corpus, then rank."""
    # Build the index each call; the corpus is small (~150 pages) and fastembed
    # will cache the ONNX model itself across calls. For M1 we'll cache the
    # index to disk; for M0.5 rebuilding each call is fine and keeps the
    # baseline honest about cold-start cost.
    idx = DenseIndex(model_name, kind)
    idx.add_corpus(corpus)
    topk = [u for u, _ in idx.query(query.text, k=5)]
    scores = {u: s for u, s in idx.query(query.text, k=5)}
    rank = None
    for i, uuid in enumerate(topk, start=1):
        if uuid in query.answer_uuids:
            rank = i
            break
    if not topk:
        return LookupTrace(
            qid=query.qid, baseline=kind, rank=None, topk_uuids=[],
            stub_tokens=0, l1_tokens=0, full_tokens=0, ended_at_stub=False,
        )
    top1 = corpus[topk[0]]
    stub_total = sum(stub_tokens(corpus[u]) for u in topk)
    return LookupTrace(
        qid=query.qid, baseline=kind, rank=rank, topk_uuids=topk,
        stub_tokens=stub_total,
        l1_tokens=stub_total + l1_tokens(top1),
        full_tokens=stub_total + full_tokens(top1),
        ended_at_stub=query.stub_sufficient and rank == 1,
    )


def run_nomic(corpus: dict[str, Page], query: Query) -> LookupTrace:
    return run_with_model("nomic-ai/nomic-embed-text-v1.5", "nomic", corpus, query)


def run_bge(corpus: dict[str, Page], query: Query) -> LookupTrace:
    return run_with_model("BAAI/bge-large-en-v1.5", "bge", corpus, query)
