from pathlib import Path

from mf import models


def test_probe_cached_needs_a_snapshot_with_the_model_file(tmp_path):
    repo = "snowflake/snowflake-arctic-embed-xs"
    assert models.probe_cached(tmp_path, repo, "onnx/model.onnx") is False
    snap = tmp_path / "models--snowflake--snowflake-arctic-embed-xs" / "snapshots" / "abc"
    (snap / "onnx").mkdir(parents=True)
    assert models.probe_cached(tmp_path, repo, "onnx/model.onnx") is False
    (snap / "onnx" / "model.onnx").write_bytes(b"x")
    assert models.probe_cached(tmp_path, repo, "onnx/model.onnx") is True


def test_is_model_cached_never_instantiates_a_model(tmp_path, monkeypatch):
    import fastembed
    monkeypatch.setattr(fastembed.TextEmbedding, "__init__", lambda *a, **k: (_ for _ in ()).throw(AssertionError("loaded a model")))
    monkeypatch.setattr(models, "fastembed_cache_dir", lambda: tmp_path)
    real = models.__dict__["is_model_cached"]
    for code in ("snowflake-arctic-embed-xs", "all-MiniLM-L6-v2", "bge-large-en-v1.5"):
        assert real(code) is False


def test_fastembed_source_resolves_registry_kinds():
    source = models.fastembed_source("arctic-xs")
    assert source is not None
    hf, model_file = source
    assert hf == "snowflake/snowflake-arctic-embed-xs" and model_file.endswith(".onnx")
    assert models.fastembed_source("minilm") is not None


def test_list_models_reports_cache_status_without_loading(monkeypatch):
    monkeypatch.setattr(models, "is_model_cached", lambda code: code.startswith("snowflake"))
    infos = {m.model_code: m for m in models.list_models()}
    assert infos["snowflake-arctic-embed-xs"].is_cached is True
    assert infos["bge-large-en-v1.5"].is_cached is False
    assert Path  # keep the import used
