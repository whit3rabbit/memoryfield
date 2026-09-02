from mf import consolidate, db, indexer, raw
from mf.schema import EMBEDDING_DIM

PAGE_ROTATE = """\
---
uuid: page-rotate
title: "How to rotate the signing key"
summary: "Run make rotate-key"
---

## Steps

Run `make rotate-key`.
"""


def _zero_vec() -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[0] = 1.0
    return vec


def _near_dup_vec() -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[0] = 1.0
    vec[-1] = 0.1
    return vec


def _far_vec() -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[1] = 1.0
    return vec


def _fake_embed_pages(pages, model_code):
    return {p.uuid: _zero_vec() for p in pages}


def _build_field(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    (tmp_path / "rotate.md").write_text(PAGE_ROTATE)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    return conn


def test_empty_raw_dir_is_an_empty_plan(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    result = consolidate.plan(tmp_path, conn)
    assert result.actions == []
    conn.close()


def test_entry_near_an_existing_page_is_review(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    raw.add_raw(tmp_path, "Turns out `make rotate-key` also needs VAULT_TOKEN set.")
    monkeypatch.setattr(consolidate.embedder, "embed_query", lambda text, model_code: _near_dup_vec())

    result = consolidate.plan(tmp_path, conn)
    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.action == "review"
    assert action.candidates[0].uuid == "page-rotate"
    conn.close()


def test_entry_far_from_everything_is_create(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    raw.add_raw(tmp_path, "The billing dunning cadence is 1/3/7/14 days.")
    monkeypatch.setattr(consolidate.embedder, "embed_query", lambda text, model_code: _far_vec())

    result = consolidate.plan(tmp_path, conn)
    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.action == "create"
    assert action.candidates == []
    conn.close()


def test_session_pointer_entry_is_reported_without_searching(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(exist_ok=True)
    (raw_dir / "20260101T000000000000Z-session.md").write_text(
        "kind: session-pointer\nsession_id: abc\ntranscript_path: /tmp/x.jsonl\n"
    )

    def _boom(text, model_code):
        raise AssertionError("pointer entries must not be embedded/searched")

    monkeypatch.setattr(consolidate.embedder, "embed_query", _boom)
    result = consolidate.plan(tmp_path, conn)
    assert len(result.actions) == 1
    assert result.actions[0].action == "pointer"
    conn.close()


def test_missing_raw_dir_is_an_empty_plan(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    result = consolidate.plan(tmp_path, conn)
    assert result.actions == []
    conn.close()
