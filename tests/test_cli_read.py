import json

from mf import cli, indexer
from mf.schema import EMBEDDING_DIM

PAGE_1 = """\
---
uuid: cli-read-001
title: "How to rotate the signing key"
summary: "Run make rotate-key"
---

## Steps

Run `make rotate-key`.

## History

Rotated quarterly since 2023.
"""

PAGE_2 = """\
---
uuid: cli-read-002
title: "How billing retries failed payments"
summary: "Dunning levels 1-4"
---

## Steps

Failed payments trigger dunning_level increments.
"""


def _fake_embed_pages(pages, model_code):
    return {p.uuid: [0.1] * EMBEDDING_DIM for p in pages}


def _build_field(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    (tmp_path / "page1.md").write_text(PAGE_1)
    (tmp_path / "page2.md").write_text(PAGE_2)
    cli.main(["init", str(tmp_path)])
    cli.main(["index", str(tmp_path)])
    capsys.readouterr()  # discard init/index output


def test_read_without_init_fails(tmp_path, capsys):
    exit_code = cli.main(["read", "anything", "--field", str(tmp_path)])
    assert exit_code == 1
    assert "mf init" in capsys.readouterr().err


def test_read_default_tier_text_output(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    exit_code = cli.main(["read", "cli-read-001", "--field", str(tmp_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "cli-read-001" in out
    assert "make rotate-key" in out
    assert "Rotated quarterly" not in out


def test_read_l2_tier(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    exit_code = cli.main(["read", "cli-read-001", "--tier", "L2", "--field", str(tmp_path)])
    assert exit_code == 0
    assert "Rotated quarterly" in capsys.readouterr().out


def test_read_section_ref(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    exit_code = cli.main(["read", "cli-read-001#history", "--field", str(tmp_path)])
    assert exit_code == 0
    assert "Rotated quarterly" in capsys.readouterr().out


def test_read_json_output(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    exit_code = cli.main(["read", "cli-read-001", "--field", str(tmp_path), "--json"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed[0]["uuid"] == "cli-read-001"
    assert parsed[0]["tier"] == "L1"


def test_read_unknown_uuid_fails(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    exit_code = cli.main(["read", "does-not-exist", "--field", str(tmp_path)])
    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_read_multiple_refs_in_one_call(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    exit_code = cli.main([
        "read", "cli-read-001", "cli-read-002", "--field", str(tmp_path), "--json",
    ])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert [r["uuid"] for r in parsed] == ["cli-read-001", "cli-read-002"]
