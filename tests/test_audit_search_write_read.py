"""Regression tests for the 2026-09-03 audit: search validation and gate
inputs, write destination safety and atomicity, read error mapping."""
from __future__ import annotations

import pytest

from mf import cli, db, indexer, read, write
from mf import search as search_mod
from tests.conftest import far_vec, one_hot

PAGE = """\
---
uuid: {uuid}
title: "{title}"
summary: "{summary}"
{extra}---

## Answer

{body}
"""


def _page(uuid, title="T", summary="S s s s s", body="body", extra=""):
    return PAGE.format(uuid=uuid, title=title, summary=summary, body=body, extra=extra)


# --- search ---------------------------------------------------------------

def test_search_rejects_bad_limits(field_factory):
    field = field_factory({"a.md": _page("a")})
    conn = db.open_field(field)
    with pytest.raises(ValueError, match="limit"):
        search_mod.search(conn, "x", limit=0)
    with pytest.raises(ValueError, match="neighbor_limit"):
        search_mod.search(conn, "x", neighbor_limit=-1)
    with pytest.raises(ValueError, match="budget"):
        search_mod.search(conn, "x", budget=-5)
    conn.close()


def test_cli_search_bad_limit_is_exit_1_not_traceback(field_factory, capsys):
    field = field_factory({"a.md": _page("a")})
    assert cli.main(["search", "x", "--field", str(field), "--limit", "-1"]) == 1
    assert "limit" in capsys.readouterr().err


def test_search_skips_the_model_when_vec_is_empty(tmp_path, monkeypatch):
    def _boom(query, model_code):
        raise AssertionError("model must not be loaded on an empty field")
    monkeypatch.setattr(search_mod, "_embed_query", _boom)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    result = search_mod.search(conn, "anything")
    assert result.results == [] and result.confidence == "none"
    conn.close()


def test_budget_skips_oversized_stub_and_keeps_smaller_one(field_factory, monkeypatch):
    big = _page("big", title="A " * 80, summary="long " * 60)
    small = _page("small", title="s", summary="tiny summary here ok")
    field = field_factory({"big.md": big, "small.md": small})
    monkeypatch.setattr(indexer, "_embed_pages", lambda pages, model_code: {p.uuid: one_hot(0 if p.uuid == "big" else 1) for p in pages})
    conn = db.open_field(field)
    indexer.index_field(field, conn)  # unchanged; vectors came from the factory
    monkeypatch.setattr(search_mod, "_embed_query", lambda q, m: one_hot(0))
    small_stub = search_mod._load_stub(conn, "small")
    assert small_stub is not None
    stub_small = search_mod._stub_cost(small_stub)
    result = search_mod.search(conn, "x", limit=2, budget=stub_small + 1)
    assert [s.uuid for s in result.results] == ["small"]
    empty = search_mod.search(conn, "x", limit=2, budget=0)
    assert empty.results == [] and empty.confidence == "none"
    conn.close()


def test_agreement_is_measured_after_supersedes_resolution(tmp_path, monkeypatch):
    """FTS top-1 on the old page and dense top-1 on its superseder is one
    answer, and the gate must count it as agreement."""
    old = _page("old", title="Rotate the signing key", summary="Run make rotate-key now please", body="make rotate-key")
    new = _page("new", title="Rotate the signing key v2", summary="Run make rotate-key-v2 now please", body="make rotate-key-v2", extra="supersedes: [old]\n")
    (tmp_path / "old.md").write_text(old)
    (tmp_path / "new.md").write_text(new)
    monkeypatch.setattr(indexer, "_embed_pages", lambda pages, model_code: {p.uuid: one_hot(0 if p.uuid == "new" else 1) for p in pages})
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    monkeypatch.setattr(search_mod, "_embed_query", lambda q, m: one_hot(1))  # dense lands on `old`
    seen = {}
    real = search_mod.confidence
    def _spy(top_score, term_count, agree, dense_distance=None):
        seen["agree"] = agree
        return real(top_score, term_count, agree, dense_distance)
    monkeypatch.setattr(search_mod, "confidence", _spy)
    # FTS: "rotate-key" as a phrase hits the old page harder (its body is the exact phrase).
    result = search_mod.search(conn, "rotate-key", limit=2)
    assert seen["agree"] is True
    assert result.results[0].uuid == "new" and result.results[0].supersedes == ["old"]
    conn.close()


# --- write ----------------------------------------------------------------

def test_write_dest_cannot_escape_the_field(field_factory, tmp_path):
    field = field_factory({"a.md": _page("a")})
    draft = tmp_path / "draft.md"
    draft.write_text(_page("d", summary="totally different words about cats"))
    conn = db.open_field(field)
    for bad in ("../evil.md", "../../evil.md", "/tmp/evil.md"):
        with pytest.raises(write.WriteValidationError):
            write.write_page(field, conn, draft, force=True, dest_name=bad)
    assert not (tmp_path / "evil.md").exists()
    conn.close()


def test_write_dest_under_skipped_dir_is_refused(field_factory, tmp_path):
    field = field_factory({"a.md": _page("a")})
    draft = tmp_path / "draft.md"
    draft.write_text(_page("d"))
    conn = db.open_field(field)
    for bad in ("raw/d.md", ".hidden/d.md", "node_modules/d.md", "d.sync-conflict-1.md"):
        with pytest.raises(write.WriteValidationError):
            write.write_page(field, conn, draft, force=True, dest_name=bad)
    conn.close()


def test_write_is_atomic_when_indexing_fails(field_factory, tmp_path, monkeypatch):
    field = field_factory({"a.md": _page("a")})
    draft = tmp_path / "draft.md"
    draft.write_text(_page("d"))
    conn = db.open_field(field)
    def _boom(*a, **k):
        raise RuntimeError("model exploded")
    monkeypatch.setattr(indexer, "index_page", _boom)
    with pytest.raises(RuntimeError):
        write.write_page(field, conn, draft, force=True)
    assert not (field / "draft.md").exists()
    assert list(field.glob(".*mf-tmp")) == []
    conn.close()


def test_write_embeds_once_per_write(field_factory, tmp_path, monkeypatch):
    field = field_factory({"a.md": _page("a")})
    draft = tmp_path / "draft.md"
    draft.write_text(_page("d"))
    calls = []
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: calls.append("gate") or far_vec())
    monkeypatch.setattr(indexer, "_embed_pages", lambda pages, model_code: calls.append("index") or {p.uuid: far_vec() for p in pages})
    conn = db.open_field(field)
    result = write.write_page(field, conn, draft)
    assert result.written and calls == ["gate"]
    assert (field / "draft.md").read_bytes() == draft.read_bytes()
    conn.close()


def test_write_dest_that_is_not_a_page_is_a_clean_error(field_factory, tmp_path):
    field = field_factory({"a.md": _page("a")})
    (field / "notes.md").write_text("# not a page\n")
    draft = tmp_path / "draft.md"
    draft.write_text(_page("d"))
    conn = db.open_field(field)
    with pytest.raises(write.WriteValidationError, match="not a memoryfield page"):
        write.write_page(field, conn, draft, force=True, dest_name="notes.md")
    conn.close()


# --- read -----------------------------------------------------------------

def test_read_rejects_unknown_tier(field_factory):
    field = field_factory({"a.md": _page("a")})
    conn = db.open_field(field)
    with pytest.raises(ValueError, match="tier"):
        read.read(conn, ["a"], tier="L3", field_dir=field)
    conn.close()


def test_read_missing_file_is_not_found_not_traceback(field_factory, capsys):
    field = field_factory({"a.md": _page("a")})
    (field / "a.md").unlink()
    conn = db.open_field(field)
    with pytest.raises(read.PageNotFoundError, match="mf index"):
        read.read(conn, ["a"], field_dir=field)
    conn.close()
    assert cli.main(["read", "a", "--field", str(field)]) == 1
    assert "not found" in capsys.readouterr().err


def test_read_l1_includes_preamble(field_factory):
    text = "---\nuuid: p\ntitle: T\n---\nPreamble line.\n\n## Answer\n\nThe answer.\n\n## More\n\nrest\n"
    field = field_factory({"p.md": text})
    conn = db.open_field(field)
    l1, = read.read(conn, ["p"], field_dir=field)
    l2, = read.read(conn, ["p"], tier="L2", field_dir=field)
    assert l1.body == "Preamble line.\n\nThe answer." and l2.body == "rest"
    conn.close()
