import json

import pytest

from mf import cli, models


def test_model_list_text(capsys):
    exit_code = cli.main(["model", "list"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "snowflake-arctic-embed-xs" in out
    assert "384" in out
    assert "* = default" in out


def test_model_list_json(capsys):
    exit_code = cli.main(["model", "list", "--json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, list)
    model_codes = [m["model_code"] for m in data]
    assert "snowflake-arctic-embed-xs" in model_codes
    assert "bge-large-en-v1.5" in model_codes
    default_model = next(m for m in data if m["is_default"])
    assert default_model["model_code"] == "snowflake-arctic-embed-xs"


def test_model_install_and_json(capsys, monkeypatch):
    monkeypatch.setattr(
        models,
        "install_model",
        lambda code: models.InstallResult(
            model_code=code, dim=384, size_mb=170, already_cached=False
        ),
    )
    exit_code = cli.main(["model", "install", "snowflake-arctic-embed-xs"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Downloaded and ready: snowflake-arctic-embed-xs (384-d, ~170 MB)" in out

    exit_code = cli.main(["model", "install", "snowflake-arctic-embed-xs", "--json"])
    assert exit_code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["model_code"] == "snowflake-arctic-embed-xs"
    assert data["already_cached"] is False


def test_model_install_rejects_unknown():
    with pytest.raises(SystemExit):
        cli.main(["model", "install", "unknown-model-xyz"])
