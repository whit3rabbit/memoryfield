import pytest

from mf import embed_backend, embedder
from mf.page import parse_page


class _FakeBackend:
    instances = 0

    def __init__(self, kind, backend=None):
        _FakeBackend.instances += 1
        self.kind = kind
        self.backend = backend
        self.seen: list[str] = []

    def embed(self, texts):
        self.seen.extend(texts)
        return [[float(len(t))] for t in texts]


@pytest.fixture
def fake_backend(monkeypatch):
    _FakeBackend.instances = 0
    monkeypatch.setattr(embed_backend, "Embedder", _FakeBackend)
    monkeypatch.setattr(embedder, "_CACHE", {})
    monkeypatch.delenv(embedder.ENV_BACKEND, raising=False)
    return _FakeBackend


def test_registry_has_models_with_dims():
    assert embedder.MODEL_REGISTRY["snowflake-arctic-embed-xs"]["kind"] == "arctic-xs"
    assert embedder.MODEL_REGISTRY["snowflake-arctic-embed-xs"]["dim"] == 384
    assert embedder.MODEL_REGISTRY["snowflake-arctic-embed-s"]["dim"] == 384
    assert embedder.MODEL_REGISTRY["bge-small-en-v1.5"]["dim"] == 384
    assert embedder.MODEL_REGISTRY["bge-large-en-v1.5"]["dim"] == 1024
    assert embedder.MODEL_REGISTRY["nomic-embed-text-v1.5"]["dim"] == 768


def test_unknown_model_code_raises():
    with pytest.raises(embedder.UnknownModelCodeError):
        embedder.registry_entry("gpt-embeddings-9000")


def test_model_is_loaded_once_per_process(fake_backend):
    embedder.embed_query("a", "nomic-embed-text-v1.5")
    embedder.embed_query("bb", "nomic-embed-text-v1.5")
    embedder.embed_texts(["ccc"], "nomic-embed-text-v1.5")
    assert fake_backend.instances == 1
    embedder.embed_query("d", "bge-large-en-v1.5")
    assert fake_backend.instances == 2


def test_query_and_document_prefixes_are_applied(fake_backend):
    embedder.embed_query("rotate key", "nomic-embed-text-v1.5")
    page = parse_page("---\nuuid: p\ntitle: T\nsummary: S\n---\n\nbody\n")
    embedder.embed_page(page, "nomic-embed-text-v1.5")
    seen = embedder.get_embedder("nomic-embed-text-v1.5").seen  # type: ignore[attr-defined]
    assert seen[0] == "search_query: rotate key"
    assert seen[1].startswith("search_document: T. S body")


def test_backend_defaults_to_fastembed_and_honors_env(fake_backend, monkeypatch):
    assert embedder.backend() == "fastembed"
    monkeypatch.setenv(embedder.ENV_BACKEND, "mlx")
    assert embedder.backend() == "mlx"
    monkeypatch.setenv(embedder.ENV_BACKEND, "gpu-magic")
    with pytest.raises(ValueError):
        embedder.backend()


def test_vec_literal_is_a_json_array():
    assert embedder.vec_literal([1.0, 0.5]) == "[1.0,0.5]"
