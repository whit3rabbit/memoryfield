import json

from mf import cli


def test_consolidate_without_plan_flag_is_an_argparse_error(tmp_path, capsys):
    import pytest

    with pytest.raises(SystemExit):
        cli.main(["consolidate", "--field", str(tmp_path)])


def test_consolidate_empty_raw_dir(tmp_path, capsys):
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()

    exit_code = cli.main(["consolidate", "--plan", "--field", str(tmp_path)])
    assert exit_code == 0
    assert "nothing to consolidate" in capsys.readouterr().out


def test_consolidate_json_output_with_no_matches(tmp_path, capsys, monkeypatch):
    from mf.schema import EMBEDDING_DIM

    cli.main(["init", str(tmp_path)])
    capsys.readouterr()
    cli.main(["raw", "add", "A freeform note nothing else is close to.", "--field", str(tmp_path)])
    capsys.readouterr()

    from mf import consolidate as consolidate_mod
    monkeypatch.setattr(consolidate_mod.embedder, "embed_query", lambda text, model_code: [0.1] * EMBEDDING_DIM)

    exit_code = cli.main(["consolidate", "--plan", "--field", str(tmp_path), "--json"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert len(parsed["actions"]) == 1
    assert parsed["actions"][0]["action"] == "create"
