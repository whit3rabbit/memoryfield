import json

from mf import cli, indexer, search
from mf.schema import EMBEDDING_DIM

PAGE_1 = """\
---
uuid: cli-search-001
title: "How to rotate the signing key"
summary: "Run make rotate-key"
---

## Steps

Run `make rotate-key`.
"""


def _fake_embed_pages(pages, model_code):
    return {p.uuid: [0.1] * EMBEDDING_DIM for p in pages}


def _fake_embed_query(query, model_code):
    return [0.1] * EMBEDDING_DIM


def _build_field(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    monkeypatch.setattr(search, "_embed_query", _fake_embed_query)
    (tmp_path / "page1.md").write_text(PAGE_1)
    cli.main(["init", str(tmp_path)])
    cli.main(["index", str(tmp_path)])
    capsys.readouterr()  # discard init/index output, isolate the search call


def test_search_without_init_fails(tmp_path, capsys):
    exit_code = cli.main(["search", "anything", "--field", str(tmp_path)])
    assert exit_code == 1
    assert "mf init" in capsys.readouterr().err


def test_search_text_output(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    exit_code = cli.main(["search", "rotate signing key", "--field", str(tmp_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "confidence:" in out
    assert "cli-search-001" in out


def test_search_json_output(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    exit_code = cli.main(["search", "rotate signing key", "--field", str(tmp_path), "--json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "confidence" in parsed
    assert parsed["results"][0]["uuid"] == "cli-search-001"


def test_search_no_fts_hit_still_returns_dense_ranking(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    # A stopwords-only query has no FTS hit at all (mf.query_prep.fts_query
    # drops every token); dense still ranks. The fake query vector equals
    # the page vector (distance 0), so the dense floor passes: low.
    exit_code = cli.main(["search", "is the a of", "--field", str(tmp_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "confidence: low" in out
    assert "cli-search-001" in out


def test_search_truly_empty_field_returns_no_results(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(search, "_embed_query", _fake_embed_query)
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()
    exit_code = cli.main(["search", "anything at all", "--field", str(tmp_path)])
    assert exit_code == 0
    assert "(no results)" in capsys.readouterr().out


def test_search_refuses_stale_index_with_exit_3(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    (tmp_path / "page1.md").write_text(PAGE_1 + "\nEdited.\n")
    exit_code = cli.main(["search", "rotate", "--field", str(tmp_path)])
    assert exit_code == 3
    assert "stale" in capsys.readouterr().err


def test_search_stale_ok_marks_results(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    (tmp_path / "page1.md").write_text(PAGE_1 + "\nEdited.\n")
    exit_code = cli.main(["search", "rotate", "--field", str(tmp_path), "--stale-ok"])
    assert exit_code == 0
    assert "(stale)" in capsys.readouterr().out
