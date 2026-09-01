import json

from mf import cli, indexer, write
from mf.schema import EMBEDDING_DIM

PAGE_ROTATE = """\
---
uuid: cli-write-rotate
title: "How to rotate the signing key"
summary: "Run make rotate-key"
---

## Steps

Run `make rotate-key`.
"""

NEW_PAGE = """\
---
uuid: cli-write-billing
title: "How billing retries failed payments"
summary: "Dunning levels 1-4"
---

## Steps

Failed payments trigger dunning_level increments.
"""


def _zero_vec():
    # One-hot on axis 0: a literal zero vector has no cosine distance.
    vec = [0.0] * EMBEDDING_DIM
    vec[0] = 1.0
    return vec


def _near_dup_vec():
    vec = [0.0] * EMBEDDING_DIM
    vec[0] = 1.0
    vec[-1] = 0.1
    return vec


def _far_vec():
    vec = [0.0] * EMBEDDING_DIM
    vec[1] = 1.0
    return vec


def _fake_embed_pages(pages, model_code):
    return {p.uuid: _zero_vec() for p in pages}


def _build_field(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    (tmp_path / "rotate.md").write_text(PAGE_ROTATE)
    cli.main(["init", str(tmp_path)])
    cli.main(["index", str(tmp_path)])
    capsys.readouterr()  # discard init/index output


def test_write_without_init_fails(tmp_path, capsys):
    (tmp_path / "new.md").write_text(NEW_PAGE)
    exit_code = cli.main(["write", str(tmp_path / "new.md"), "--field", str(tmp_path)])
    assert exit_code == 1
    assert "mf init" in capsys.readouterr().err


def test_write_new_page_succeeds(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _far_vec())
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    exit_code = cli.main(["write", str(tmp_path / "billing.md"), "--field", str(tmp_path)])
    assert exit_code == 0
    assert "Wrote cli-write-billing" in capsys.readouterr().out


def test_write_blocks_near_duplicate_with_exit_code_2(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _near_dup_vec())
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    exit_code = cli.main(["write", str(tmp_path / "billing.md"), "--field", str(tmp_path)])
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "near-duplicate" in out
    assert "cli-write-rotate" in out


def test_write_force_flag(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _near_dup_vec())
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    exit_code = cli.main([
        "write", str(tmp_path / "billing.md"), "--field", str(tmp_path), "--force",
    ])
    assert exit_code == 0


def test_write_json_output(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _far_vec())
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    exit_code = cli.main([
        "write", str(tmp_path / "billing.md"), "--field", str(tmp_path), "--json",
    ])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["written"] is True
    assert parsed["uuid"] == "cli-write-billing"


def test_write_update_uuid_mismatch_fails(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    exit_code = cli.main([
        "write", str(tmp_path / "billing.md"), "--field", str(tmp_path), "--update", "wrong-uuid",
    ])
    assert exit_code == 1
    assert "doesn't match" in capsys.readouterr().err
