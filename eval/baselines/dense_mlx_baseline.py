"""Dense baselines using the MLX backend (mf.embed_backend), Apple Silicon only.

Same models and same document/query text prep as dense_real_baseline.py
(nomic-embed-text-v1.5, bge-large-en-v1.5); only the embedding runtime
differs (MLX/Metal here, fastembed/ONNX there), so results are directly
comparable. run_baselines.py registers these baselines only when
mf.embed_backend.mlx_available() is true; on any other platform they're
skipped, and the fastembed dense_nomic/dense_bge baselines remain the
fallback.
"""
from __future__ import annotations

from mf.embed_backend import Embedder
from mf.embedding import document_text, query_text

from ..mf_harness import LookupTrace, Page, Query, full_tokens, l1_tokens, stub_tokens


def _normalize(matrix) -> list[list[float]]:
    import numpy as np
    arr = np.asarray(matrix, dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (arr / norms).tolist()


class MlxDenseIndex:
    """Pre-computed embeddings for a corpus, via the MLX backend."""

    def __init__(self, kind: str):
        self.kind = kind  # "nomic" or "bge"
        self.embedder = Embedder(kind, backend="mlx")
        self._page_vecs: list[list[float]] = []
        self._page_ids: list[str] = []

    def add_corpus(self, corpus: dict[str, Page]) -> None:
        texts = []
        ids = []
        for uuid, page in corpus.items():
            l1 = page.body_l1 if page.body_sections else ""
            texts.append(document_text(page.title, page.summary, l1, self.kind))
            ids.append(uuid)
        if not texts:
            return
        vecs = self.embedder.embed(texts)
        self._page_vecs = _normalize(vecs)
        self._page_ids = ids

    def query(self, q: str, k: int = 5) -> list[tuple[str, float]]:
        import numpy as np
        qv = self.embedder.embed([query_text(q, self.kind)])
        qv = _normalize(qv)[0]
        page_mat = np.asarray(self._page_vecs, dtype="float32")
        scores = page_mat @ np.asarray(qv, dtype="float32")
        order = np.argsort(-scores)[:k]
        return [(self._page_ids[i], float(scores[i])) for i in order]


def run_with_model(kind: str, corpus: dict[str, Page], query: Query) -> LookupTrace:
    idx = MlxDenseIndex(kind)
    idx.add_corpus(corpus)
    topk = [u for u, _ in idx.query(query.text, k=5)]
    rank = None
    for i, uuid in enumerate(topk, start=1):
        if uuid in query.answer_uuids:
            rank = i
            break
    if not topk:
        return LookupTrace(
            qid=query.qid, baseline=f"mlx_{kind}", rank=None, topk_uuids=[],
            stub_tokens=0, l1_tokens=0, full_tokens=0, ended_at_stub=False,
        )
    top1 = corpus[topk[0]]
    stub_total = sum(stub_tokens(corpus[u]) for u in topk)
    return LookupTrace(
        qid=query.qid, baseline=f"mlx_{kind}", rank=rank, topk_uuids=topk,
        stub_tokens=stub_total,
        l1_tokens=stub_total + l1_tokens(top1),
        full_tokens=stub_total + full_tokens(top1),
        ended_at_stub=query.stub_sufficient and rank == 1,
    )


def run_nomic(corpus: dict[str, Page], query: Query) -> LookupTrace:
    return run_with_model("nomic", corpus, query)


def run_bge(corpus: dict[str, Page], query: Query) -> LookupTrace:
    return run_with_model("bge", corpus, query)
