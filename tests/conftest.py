"""Shared fixtures. The embedding model is never loaded in tests: every
path that would reach fastembed is a module-level function the fixtures
below replace with a deterministic stand-in. Dimension must match
schema.EMBEDDING_DIM (the vec0 table's fixed width) or sqlite-vec rejects
the insert.

One deliberate exception: tests/test_token_regression.py loads the real
model, since a token-cost/correctness regression check is meaningless
against fake constant vectors.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mf import cli, embedder, indexer, models
from mf import pack as pack_mod
from mf import search as search_mod
from mf import write as write_mod
from mf.schema import EMBEDDING_DIM


@pytest.fixture(autouse=True)
def _isolate_embedder(monkeypatch):
    """No test inherits another's loaded model, backend env, or a real
    probe of the fastembed cache on this machine."""
    monkeypatch.setattr(embedder, "_CACHE", {})
    monkeypatch.delenv(embedder.ENV_BACKEND, raising=False)
    monkeypatch.setattr(models, "is_model_cached", lambda model_code: False)


def one_hot(i: int, dim: int = EMBEDDING_DIM) -> list[float]:
    vec = [0.0] * dim
    vec[i % dim] = 1.0
    return vec


def zero_vec() -> list[float]:
    """The 'existing page' vector: one-hot on axis 0. Not literally zero,
    since a zero vector has no cosine distance (gotcha 32)."""
    return one_hot(0)


def near_dup_vec() -> list[float]:
    """Cosine distance ~0.005 from zero_vec(), under DEDUP_THRESHOLD."""
    vec = one_hot(0)
    vec[1] = 0.1
    return vec


def far_vec() -> list[float]:
    """Orthogonal to zero_vec(): cosine distance 1.0."""
    return one_hot(1)


def const_vec() -> list[float]:
    return [0.1] * EMBEDDING_DIM


@pytest.fixture
def fake_embeddings(monkeypatch):
    """Constant vectors on every embedding path: index, search, write's
    gate, pack --spec. Enough for tests that need an indexed field and
    don't care about distances."""
    monkeypatch.setattr(indexer, "_embed_pages", lambda pages, model_code: {p.uuid: const_vec() for p in pages})
    monkeypatch.setattr(search_mod, "_embed_query", lambda query, model_code: const_vec())
    monkeypatch.setattr(write_mod, "_embed_page", lambda page, model_code: const_vec())
    monkeypatch.setattr(pack_mod, "_embed_texts", lambda texts, model_code: [const_vec() for _ in texts])


@pytest.fixture
def field_factory(tmp_path, fake_embeddings, capsys):
    """`build({"name.md": text, ...}) -> field dir`, initialized and
    indexed through the CLI with fake embeddings."""
    def build(pages: dict[str, str], name: str = "field") -> Path:
        field = tmp_path / name
        field.mkdir()
        for rel, text in pages.items():
            path = field / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        assert cli.main(["init", str(field)]) == 0
        assert cli.main(["index", str(field)]) == 0
        capsys.readouterr()
        return field
    return build
