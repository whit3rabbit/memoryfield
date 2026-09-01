import json

from mf import cli, indexer
from mf.schema import EMBEDDING_DIM

PAGE = "---\nuuid: p1\ntitle: \"T\"\nsummary: \"S\"\n---\n\n## Answer\n\nbody\n"


def _field(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", lambda pages, model_code: {p.uuid: [0.1] * EMBEDDING_DIM for p in pages})
    field = tmp_path / "field"
    field.mkdir()
    (field / "p1.md").write_text(PAGE)
    cli.main(["init", str(field)])
    cli.main(["index", str(field)])
    return field


def test_pack_then_unpack_cli(tmp_path, capsys, monkeypatch):
    field = _field(tmp_path, monkeypatch)
    capsys.readouterr()
    assert cli.main(["pack", str(field)]) == 0
    out = capsys.readouterr().out
    assert "field.memoryfield.zip" in out and "sha256" in out
    archive = tmp_path / "field.memoryfield.zip"
    assert archive.exists() and archive.with_name("field.memoryfield.zip.sha256").exists()

    assert cli.main(["unpack", str(archive), str(tmp_path / "restored"), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["verified"] is True and parsed["has_index"] is True and parsed["index_drift"] == 0
    assert (tmp_path / "restored" / "p1.md").read_text() == PAGE


def test_unpack_tampered_exits_2(tmp_path, capsys, monkeypatch):
    field = _field(tmp_path, monkeypatch)
    cli.main(["pack", str(field)])
    archive = tmp_path / "field.memoryfield.zip"
    with archive.open("ab") as f:
        f.write(b"x")
    assert cli.main(["unpack", str(archive), str(tmp_path / "r")]) == 2
    assert "does not match" in capsys.readouterr().err


def test_unpack_missing_archive_exits_1(tmp_path, capsys):
    assert cli.main(["unpack", str(tmp_path / "nope.zip"), str(tmp_path / "r")]) == 1
