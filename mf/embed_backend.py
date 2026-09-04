"""Embedding backend selection: MLX on Apple Silicon, fastembed elsewhere.

`mlx-embedding-models` runs the exact same checkpoints as the fastembed
baselines (see its registry: "nomic-text-v1.5" -> nomic-ai/nomic-embed-text-v1.5,
"bge-large" -> BAAI/bge-large-en-v1.5) on the Metal GPU via MLX, but MLX
itself only runs on Apple Silicon. fastembed (ONNX Runtime, CPU) is the
cross-platform fallback and stays the default everywhere else.
"""
from __future__ import annotations

import platform
from importlib.util import find_spec
from typing import Any, Literal

Backend = Literal["mlx", "fastembed"]

# kind -> per-backend model identifier.
_MLX_REGISTRY: dict[str, str] = {"nomic": "nomic-text-v1.5", "bge": "bge-large"}
_FASTEMBED_MODEL: dict[str, str] = {
    "arctic-xs": "snowflake/snowflake-arctic-embed-xs",
    "arctic-s": "snowflake/snowflake-arctic-embed-s",
    "bge-small": "BAAI/bge-small-en-v1.5",
    "bge-base": "BAAI/bge-base-en-v1.5",
    "bge": "BAAI/bge-large-en-v1.5",
    "nomic": "nomic-ai/nomic-embed-text-v1.5",
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
    "jina-small": "jinaai/jina-embeddings-v2-small-en",
}


def fastembed_model_name(kind: str) -> str:
    """The fastembed `model_name` for a registry kind."""
    if kind not in _FASTEMBED_MODEL:
        raise ValueError(f"fastembed backend does not support kind: {kind!r}")
    return _FASTEMBED_MODEL[kind]


def mlx_supports(kind: str) -> bool:
    return kind in _MLX_REGISTRY


def apple_silicon() -> bool:
    """True on macOS running on arm64 (Apple Silicon), false everywhere else."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def mlx_available() -> bool:
    """True if the MLX backend can actually be used: Apple Silicon macOS
    plus `mlx_embedding_models` installed (the `mlx` extra)."""
    return apple_silicon() and find_spec("mlx_embedding_models") is not None


def default_backend() -> Backend:
    return "mlx" if mlx_available() else "fastembed"


class Embedder:
    """Uniform `embed(texts) -> list[list[float]]` over either backend.

    `kind` matches mf.embedding's model_kind. The backend is chosen by
    mf.embedder.backend(); this class only checks the request is
    satisfiable.
    """

    def __init__(self, kind: str, backend: Backend):
        if kind not in _FASTEMBED_MODEL and kind not in _MLX_REGISTRY:
            raise ValueError(f"unknown model kind: {kind!r}")
        self.kind = kind
        self.backend: Backend = backend
        self._model: Any

        if backend == "mlx":
            if kind not in _MLX_REGISTRY:
                raise ValueError(f"mlx backend only supports {list(_MLX_REGISTRY)}, not {kind!r}")
            if not mlx_available():
                raise RuntimeError(
                    "mlx backend requested but unavailable: needs Apple "
                    "Silicon macOS and `uv sync --extra mlx`"
                )
            from mlx_embedding_models.embedding import EmbeddingModel  # pyright: ignore[reportMissingImports]
            self._model = EmbeddingModel.from_registry(_MLX_REGISTRY[kind])
        elif backend == "fastembed":
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=fastembed_model_name(kind))
        else:
            raise ValueError(f"unknown backend: {backend!r}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.backend == "mlx":
            return self._model.encode(texts).tolist()
        return [list(v) for v in self._model.embed(texts, batch_size=32)]
