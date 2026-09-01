import pytest

from mf import cli, indexer

PAGE_1 = """\
---
uuid: cli-001
title: "CLI test page"
summary: "A test page"
---

## Body

Some content.
"""


def _fake_embed_pages(pages, model_code):
    from mf.schema import EMBEDDING_DIM
    return {p.uuid: [0.1] * EMBEDDING_DIM for p in pages}


def test_init_creates_field(tmp_path, capsys):
    exit_code = cli.main(["init", str(tmp_path)])
    assert exit_code == 0
    assert (tmp_path / "mf.sqlite3").exists()
    assert "Initialized" in capsys.readouterr().out


def test_init_twice_fails_without_overwriting(tmp_path, capsys):
    cli.main(["init", str(tmp_path)])
    exit_code = cli.main(["init", str(tmp_path)])
    assert exit_code == 1
    assert "already exists" in capsys.readouterr().err


def test_index_without_init_fails(tmp_path, capsys):
    exit_code = cli.main(["index", str(tmp_path)])
    assert exit_code == 1
    assert "mf init" in capsys.readouterr().err


def test_index_reports_counts(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    (tmp_path / "page1.md").write_text(PAGE_1)
    cli.main(["init", str(tmp_path)])

    exit_code = cli.main(["index", str(tmp_path)])
    assert exit_code == 0
    assert "1 upserted, 0 unchanged, 0 deleted" in capsys.readouterr().out

    exit_code = cli.main(["index", str(tmp_path)])
    assert exit_code == 0
    assert "0 upserted, 1 unchanged, 0 deleted" in capsys.readouterr().out


def test_init_with_bge_sets_dim_and_vec_width(tmp_path, capsys):
    from mf import db, schema

    exit_code = cli.main(["init", str(tmp_path), "--model", "bge-large-en-v1.5"])
    assert exit_code == 0
    assert "1024-d" in capsys.readouterr().out
    conn = db.open_field(tmp_path)
    assert schema.get_config(conn, "model_code") == "bge-large-en-v1.5"
    assert schema.get_config(conn, "embedding_dim") == "1024"
    conn.execute("INSERT INTO vec VALUES ('p', ?)", ("[" + ",".join(["0.1"] * 1024) + "]",))
    conn.close()


def test_init_rejects_unknown_model(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cli.main(["init", str(tmp_path), "--model", "nope"])
    assert "invalid choice" in capsys.readouterr().err
