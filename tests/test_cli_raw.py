import io
import json

from mf import cli


def test_raw_add_without_init_fails(tmp_path, capsys):
    exit_code = cli.main(["raw", "add", "some text", "--field", str(tmp_path)])
    assert exit_code == 1
    assert "mf init" in capsys.readouterr().err


def test_raw_add_positional_text(tmp_path, capsys):
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()

    exit_code = cli.main(["raw", "add", "Session extract text.", "--field", str(tmp_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Appended to" in out
    entries = list((tmp_path / "raw").glob("*.md"))
    assert len(entries) == 1
    assert entries[0].read_text(encoding="utf-8").strip() == "Session extract text."


def test_raw_add_reads_stdin_when_no_positional_arg(tmp_path, capsys, monkeypatch):
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()
    monkeypatch.setattr("sys.stdin", io.StringIO("Piped session extract."))

    exit_code = cli.main(["raw", "add", "--field", str(tmp_path)])
    assert exit_code == 0
    entries = list((tmp_path / "raw").glob("*.md"))
    assert entries[0].read_text(encoding="utf-8").strip() == "Piped session extract."


def test_raw_add_duplicate_is_skipped(tmp_path, capsys):
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()
    cli.main(["raw", "add", "Same extract.", "--field", str(tmp_path)])
    capsys.readouterr()

    exit_code = cli.main(["raw", "add", "Same extract.", "--field", str(tmp_path)])
    assert exit_code == 0
    assert "Skipped" in capsys.readouterr().out
    assert len(list((tmp_path / "raw").glob("*.md"))) == 1


def test_raw_add_json_output(tmp_path, capsys):
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()

    exit_code = cli.main(["raw", "add", "Extract.", "--field", str(tmp_path), "--json"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["written"] is True
    assert "path" in parsed


def test_raw_dir_never_indexed(tmp_path, capsys, monkeypatch):
    from mf.schema import EMBEDDING_DIM

    def _fake_embed_pages(pages, model_code):
        return {p.uuid: [0.1] * EMBEDDING_DIM for p in pages}

    from mf import indexer
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)

    cli.main(["init", str(tmp_path)])
    capsys.readouterr()
    cli.main(["raw", "add", "---\nuuid: fake\ntitle: sneaky\n---\nbody", "--field", str(tmp_path)])
    capsys.readouterr()

    exit_code = cli.main(["index", str(tmp_path)])
    assert exit_code == 0
    assert "0 upserted" in capsys.readouterr().out
