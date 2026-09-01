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
from typing import Literal

Backend = Literal["mlx", "fastembed"]

# kind -> per-backend model identifier. Both point at the same underlying
# HF checkpoint; only the runtime differs.
_MLX_REGISTRY: dict[str, str] = {"nomic": "nomic-text-v1.5", "bge": "bge-large"}
_FASTEMBED_MODEL: dict[str, str] = {
    "nomic": "nomic-ai/nomic-embed-text-v1.5",
    "bge": "BAAI/bge-large-en-v1.5",
}


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

    `kind` is "nomic" or "bge", matching mf.embedding's model_kind. Backend
    defaults to auto-detected (MLX on Apple Silicon if installed, fastembed
    otherwise) but can be forced for testing or comparison runs.
    """

    def __init__(self, kind: str, backend: Backend | None = None):
        if kind not in _MLX_REGISTRY:
            raise ValueError(f"unknown model kind: {kind!r}")
        self.kind = kind
        self.backend: Backend = backend or default_backend()

        if self.backend == "mlx":
            if not mlx_available():
                raise RuntimeError(
                    "mlx backend requested but unavailable: needs Apple "
                    "Silicon macOS and `uv sync --extra mlx`"
                )
            from mlx_embedding_models.embedding import EmbeddingModel
            self._model = EmbeddingModel.from_registry(_MLX_REGISTRY[kind])
        elif self.backend == "fastembed":
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=_FASTEMBED_MODEL[kind])
        else:
            raise ValueError(f"unknown backend: {self.backend!r}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.backend == "mlx":
            return self._model.encode(texts).tolist()
        return list(self._model.embed(texts, batch_size=32))
