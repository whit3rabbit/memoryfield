"""`mf model list` and `mf model install` commands.

"Is this model downloaded?" is answered from the filesystem, never by
instantiating the model: fastembed's TextEmbedding loads the ONNX
session on construction, and constructing several in one process is
exactly what CLAUDE.md gotcha 4 warns deadlocks. The first version of
`mf model list` did that for all eight registry entries.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mf import embed_backend, embedder
from mf.schema import DEFAULT_MODEL_CODE


@dataclass
class ModelInfo:
    model_code: str
    dim: int
    size_mb: int
    speed: str
    description: str
    is_default: bool
    is_cached: bool

    def as_dict(self) -> dict:
        return {
            "model_code": self.model_code,
            "dim": self.dim,
            "size_mb": self.size_mb,
            "speed": self.speed,
            "description": self.description,
            "is_default": self.is_default,
            "is_cached": self.is_cached,
        }


def fastembed_cache_dir() -> Path:
    from fastembed.common.utils import define_cache_dir
    return Path(define_cache_dir())


def fastembed_source(kind: str) -> tuple[str, str] | None:
    """(HuggingFace repo, model file) fastembed downloads for `kind`, or
    None when fastembed's own registry doesn't list the model."""
    from fastembed import TextEmbedding
    name = embed_backend.fastembed_model_name(kind)
    for entry in TextEmbedding.list_supported_models():
        if entry.get("model") == name:
            sources = entry.get("sources") or {}
            hf = sources.get("hf")
            model_file = entry.get("model_file") or "model.onnx"
            return (hf, model_file) if hf else None
    return None


def probe_cached(cache_dir: Path, hf_repo: str, model_file: str) -> bool:
    """True when a HuggingFace-layout snapshot of `hf_repo` under
    `cache_dir` contains `model_file`. Pure filesystem check."""
    snapshots = cache_dir / f"models--{hf_repo.replace('/', '--')}" / "snapshots"
    try:
        return any((snap / model_file).is_file() for snap in snapshots.iterdir())
    except OSError:
        return False


def is_model_cached(model_code: str) -> bool:
    """Check whether the weights are already in the local fastembed cache."""
    kind = embedder.registry_entry(model_code)["kind"]
    source = fastembed_source(kind)
    if source is None:
        return False
    return probe_cached(fastembed_cache_dir(), *source)


def list_models() -> list[ModelInfo]:
    """Return catalog of available models with metadata and cache status."""
    items = []
    for code, info in embedder.MODEL_REGISTRY.items():
        items.append(
            ModelInfo(
                model_code=code,
                dim=info["dim"],
                size_mb=info.get("size_mb", 0),
                speed=info.get("speed", ""),
                description=info.get("description", ""),
                is_default=(code == DEFAULT_MODEL_CODE),
                is_cached=is_model_cached(code),
            )
        )
    return items


@dataclass
class InstallResult:
    model_code: str
    dim: int
    size_mb: int
    already_cached: bool

    def as_dict(self) -> dict:
        return {
            "model_code": self.model_code,
            "dim": self.dim,
            "size_mb": self.size_mb,
            "already_cached": self.already_cached,
        }


def install_model(model_code: str) -> InstallResult:
    """Download and warm up model weights into cache. The model is
    instantiated exactly once."""
    entry = embedder.registry_entry(model_code)
    was_cached = is_model_cached(model_code)
    emb = embedder.get_embedder(model_code)
    _ = emb.embed(["test warmup"])
    return InstallResult(
        model_code=model_code,
        dim=entry["dim"],
        size_mb=entry.get("size_mb", 0),
        already_cached=was_cached,
    )
