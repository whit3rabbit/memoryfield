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


def _fake_embed_query(query, model_kind, model_name):
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


def test_search_no_fts_hit_falls_back_to_dense_with_none_confidence(tmp_path, capsys, monkeypatch):
    _build_field(tmp_path, monkeypatch, capsys)
    # A stopwords-only query has no FTS hit at all (mf.query_prep.fts_query
    # drops every token); search still returns dense's best-effort
    # candidate rather than nothing, but flags confidence: none.
    exit_code = cli.main(["search", "is the a of", "--field", str(tmp_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "confidence: none" in out
    assert "cli-search-001" in out


def test_search_truly_empty_field_returns_no_results(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(search, "_embed_query", _fake_embed_query)
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()
    exit_code = cli.main(["search", "anything at all", "--field", str(tmp_path)])
    assert exit_code == 0
    assert "(no results)" in capsys.readouterr().out
