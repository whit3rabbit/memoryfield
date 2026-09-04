import pytest

from mf import embed_backend
from mf.embed_backend import Embedder, apple_silicon, default_backend, mlx_available


def test_apple_silicon_true_on_darwin_arm64(monkeypatch):
    monkeypatch.setattr(embed_backend.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(embed_backend.platform, "machine", lambda: "arm64")
    assert apple_silicon() is True


def test_apple_silicon_false_on_darwin_intel(monkeypatch):
    monkeypatch.setattr(embed_backend.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(embed_backend.platform, "machine", lambda: "x86_64")
    assert apple_silicon() is False


def test_apple_silicon_false_on_linux(monkeypatch):
    monkeypatch.setattr(embed_backend.platform, "system", lambda: "Linux")
    monkeypatch.setattr(embed_backend.platform, "machine", lambda: "arm64")
    assert apple_silicon() is False


def test_mlx_available_false_when_package_missing(monkeypatch):
    monkeypatch.setattr(embed_backend, "apple_silicon", lambda: True)
    monkeypatch.setattr(embed_backend, "find_spec", lambda name: None)
    assert mlx_available() is False


def test_mlx_available_false_off_apple_silicon_even_if_package_present(monkeypatch):
    monkeypatch.setattr(embed_backend, "apple_silicon", lambda: False)
    monkeypatch.setattr(embed_backend, "find_spec", lambda name: object())
    assert mlx_available() is False


def test_mlx_available_true_when_both_conditions_hold(monkeypatch):
    monkeypatch.setattr(embed_backend, "apple_silicon", lambda: True)
    monkeypatch.setattr(embed_backend, "find_spec", lambda name: object())
    assert mlx_available() is True


def test_default_backend_prefers_mlx_when_available(monkeypatch):
    monkeypatch.setattr(embed_backend, "mlx_available", lambda: True)
    assert default_backend() == "mlx"


def test_default_backend_falls_back_to_fastembed(monkeypatch):
    monkeypatch.setattr(embed_backend, "mlx_available", lambda: False)
    assert default_backend() == "fastembed"


def test_embedder_rejects_unknown_kind():
    with pytest.raises(ValueError):
        Embedder("unknown", backend="fastembed")


def test_embedder_rejects_mlx_backend_when_unavailable(monkeypatch):
    monkeypatch.setattr(embed_backend, "mlx_available", lambda: False)
    with pytest.raises(RuntimeError):
        Embedder("nomic", backend="mlx")
