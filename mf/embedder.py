"""One embedding entry point for `mf index`, `mf search`, `mf write`,
and `mf consolidate` (ROADMAP.md 2.9).

Before this module each of the three instantiated `fastembed.TextEmbedding`
itself and carried its own copy of the vector literal, the single-source-
of-truth drift the roadmap's checklist warns about (and `mf write`
loaded the model twice per call: once for the gate, once to index).
Text construction and model prefixes stay in mf/embedding.py; this
module owns the model registry, the model cache, and the vector blob
sqlite-vec expects.

Backend: fastembed (ONNX, CPU) always, unless `MF_EMBED_BACKEND=mlx`
is set and mf/embed_backend.py says MLX is available for that model
kind. Not auto-selected: an index's vectors must all come from one
runtime, and the two runtimes' outputs for the same checkpoint differ
slightly, so switching silently between machines would shift every
distance the gate is calibrated on. A kind MLX cannot serve falls back
to fastembed with a warning rather than failing every command. The
backend isn't recorded in `config` yet; if MLX ever becomes the
default, add it next to `model_code`.

Which side of an asymmetric model a text is embedded on matters as much
as the model: `DEDUP_THRESHOLD` and `REVIEW_THRESHOLD` were calibrated
document-to-document, so anything compared against them goes through
`embed_page`/`embed_document`, never `embed_query` (CLAUDE.md gotcha
32's family).
"""
from __future__ import annotations

import math
import os
import sys
import threading

import sqlite_vec

from . import embed_backend
from .embedding import document_text, query_text
from .page import Page

# Spec model_code (docs/architecture.md, PLAN.md's embedder table) -> the
# prefix "kind" mf/embedding.py keys on, and the vector width the `vec`
# table is created with by `mf init --model`.
MODEL_REGISTRY: dict[str, dict] = {
    "snowflake-arctic-embed-xs": {
        "kind": "arctic-xs",
        "dim": 384,
        "size_mb": 170,
        "speed": "0.9 ms",
        "description": "Default: ultra-fast 384-d, high accuracy (0.950 top-1)",
    },
    "snowflake-arctic-embed-s": {
        "kind": "arctic-s",
        "dim": 384,
        "size_mb": 255,
        "speed": "1.8 ms",
        "description": "Highest blind accuracy (0.975 top-1), fast 384-d",
    },
    "bge-small-en-v1.5": {
        "kind": "bge-small",
        "dim": 384,
        "size_mb": 130,
        "speed": "2.4 ms",
        "description": "Compact, balanced retrieval (0.950 top-1)",
    },
    "all-MiniLM-L6-v2": {
        "kind": "minilm",
        "dim": 384,
        "size_mb": 170,
        "speed": "3.1 ms",
        "description": "Ultra-lightweight baseline (0.925 blind top-1)",
    },
    "jina-embeddings-v2-small-en": {
        "kind": "jina-small",
        "dim": 512,
        "size_mb": 250,
        "speed": "0.9 ms",
        "description": "512-d output, 8192-token context window",
    },
    "bge-base-en-v1.5": {
        "kind": "bge-base",
        "dim": 768,
        "size_mb": 420,
        "speed": "5.9 ms",
        "description": "768-d baseline (0.925 top-1)",
    },
    "nomic-embed-text-v1.5": {
        "kind": "nomic",
        "dim": 768,
        "size_mb": 520,
        "speed": "4.6 ms",
        "description": "768-d asymmetric model, 8192-token context",
    },
    "bge-large-en-v1.5": {
        "kind": "bge",
        "dim": 1024,
        "size_mb": 2500,
        "speed": "12.6 ms",
        "description": "1024-d high-capacity model (0.950 top-1)",
    },
}

ENV_BACKEND = "MF_EMBED_BACKEND"


class UnknownModelCodeError(ValueError):
    pass


def registry_entry(model_code: str) -> dict:
    if model_code not in MODEL_REGISTRY:
        raise UnknownModelCodeError(
            f"unknown model_code {model_code!r}; known: {list(MODEL_REGISTRY)}"
        )
    return MODEL_REGISTRY[model_code]


def backend(kind: str | None = None) -> embed_backend.Backend:
    """The backend `MF_EMBED_BACKEND` asks for, checked against `kind`
    when one is given: MLX serves only the kinds in its registry."""
    requested = os.environ.get(ENV_BACKEND, "fastembed")
    if requested == "fastembed":
        return "fastembed"
    if requested != "mlx":
        raise ValueError(f"{ENV_BACKEND} must be 'fastembed' or 'mlx', not {requested!r}")
    if kind is not None and not embed_backend.mlx_supports(kind):
        sys.stderr.write(
            f"mf: {ENV_BACKEND}=mlx but MLX has no {kind!r} model; using fastembed\n"
        )
        return "fastembed"
    return "mlx"


_CACHE: dict[tuple[str, str], embed_backend.Embedder] = {}
# fastembed's TextEmbedding is not safe to instantiate twice concurrently
# in one process (CLAUDE.md gotcha 4), and the MCP server runs tools on
# worker threads, so the cache fill is serialized.
_CACHE_LOCK = threading.Lock()


def get_embedder(model_code: str) -> embed_backend.Embedder:
    """The loaded model for `model_code`, one per process. Loading is
    the dominant cost of a CLI call (seconds), so nothing should ask for
    a model twice.
    """
    kind = registry_entry(model_code)["kind"]
    key = (kind, backend(kind))
    if key in _CACHE:
        return _CACHE[key]
    with _CACHE_LOCK:
        if key not in _CACHE:
            _CACHE[key] = embed_backend.Embedder(kind, backend=key[1])
        return _CACHE[key]


def embed_texts(texts: list[str], model_code: str) -> list[list[float]]:
    if not texts:
        return []
    vectors = get_embedder(model_code).embed(texts)
    return [[float(x) for x in v] for v in vectors]


def embed_query(query: str, model_code: str) -> list[float]:
    """Query-side embedding: for comparing a question against pages."""
    kind = registry_entry(model_code)["kind"]
    return embed_texts([query_text(query, kind)], model_code)[0]


def embed_documents(texts: list[str], model_code: str) -> list[list[float]]:
    """Document-side embedding of free text (no title/summary structure):
    for comparing a draft or a raw extract against pages on the same
    side of the model the pages themselves were embedded on."""
    kind = registry_entry(model_code)["kind"]
    return embed_texts([document_text("", "", t, kind) for t in texts], model_code)


def embed_document(text: str, model_code: str) -> list[float]:
    return embed_documents([text], model_code)[0]


def embed_pages(pages: list[Page], model_code: str) -> dict[str, list[float]]:
    kind = registry_entry(model_code)["kind"]
    texts = [document_text(p.title, p.summary, p.l1, kind) for p in pages]
    return {p.uuid: v for p, v in zip(pages, embed_texts(texts, model_code), strict=True)}


def embed_page(page: Page, model_code: str) -> list[float]:
    return embed_pages([page], model_code)[page.uuid]


def vec_blob(vector: list[float]) -> bytes:
    """The float32 blob sqlite-vec accepts for a MATCH or INSERT. Exact
    (no text round-trip through 17-digit reprs) and a quarter the size of
    the JSON form this used to emit. A non-finite component is refused
    here with a readable error instead of a sqlite-vec parse error.
    """
    if any(not math.isfinite(v) for v in vector):
        raise ValueError("embedding contains a non-finite value")
    return sqlite_vec.serialize_float32(vector)


# Older name, kept for the eval scripts. Same bytes.
vec_literal = vec_blob
