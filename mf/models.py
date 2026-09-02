"""`mf model list` and `mf model install` commands."""
from __future__ import annotations

from dataclasses import dataclass

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


def is_model_cached(model_code: str) -> bool:
    """Check if model weights are already downloaded in local cache."""
    entry = embedder.registry_entry(model_code)
    fastembed_name = embed_backend._FASTEMBED_MODEL.get(entry["kind"])
    if not fastembed_name:
        return False
    try:
        from fastembed import TextEmbedding
        TextEmbedding(model_name=fastembed_name, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def list_models() -> list[ModelInfo]:
    """Return catalog of available models with metadata and cache status."""
    items = []
    for code, info in embedder.MODEL_REGISTRY.items():
        cached = is_model_cached(code)
        items.append(
            ModelInfo(
                model_code=code,
                dim=info["dim"],
                size_mb=info.get("size_mb", 0),
                speed=info.get("speed", ""),
                description=info.get("description", ""),
                is_default=(code == DEFAULT_MODEL_CODE),
                is_cached=cached,
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
    """Download and warm up model weights into cache."""
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
