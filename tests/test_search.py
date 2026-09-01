import functools

from mf import confidence as confidence_mod
from mf import db, indexer, search
from mf.schema import EMBEDDING_DIM

# This 4-page test corpus is far smaller than the 157-page corpus the
# real floor (2.0) was calibrated against; bm25 magnitude scales with
# corpus size (see eval/calibrate_confidence.py), so normalized scores
# here never clear the real floor. Tests that specifically exercise the
# high/low agreement decision (not floor calibration, which is
# unit-tested directly in test_confidence.py) use floor=0.0 so the
# floor check itself never masks what's being tested.
_low_floor_confidence = functools.partial(confidence_mod.confidence, floor=0.0)  # FTS floor always passes

PAGE_ROTATE = """\
---
uuid: page-rotate
title: "How to rotate the signing key"
summary: "Run make rotate-key"
---

## Steps

Run `make rotate-key`.
"""

PAGE_ROTATE_OLD = """\
---
uuid: page-rotate-old
title: "How to rotate keys (old process)"
summary: "Deprecated manual process"
status: superseded
---

## Steps

SSH in and edit the config by hand.
"""

PAGE_ROTATE_NEW = """\
---
uuid: page-rotate-new
title: "How to rotate the signing key (current)"
summary: "Current process, supersedes the old one"
supersedes: [page-rotate-old]
---

## Steps

Run `make rotate-key`.
"""

PAGE_BILLING = """\
---
uuid: page-billing
title: "How billing retries failed payments"
summary: "Dunning levels 1-4"
---

## Steps

Failed payments trigger dunning_level increments.
"""


def _one_hot(index: int) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[index] = 1.0
    return vec


# One fixed, distinct vector per uuid, so KNN queries are deterministic.
_PAGE_VECTORS = {
    "page-rotate": _one_hot(0),
    "page-rotate-old": _one_hot(1),
    "page-rotate-new": _one_hot(2),
    "page-billing": _one_hot(3),
}


def _fake_embed_pages(pages, model_code):
    return {p.uuid: _PAGE_VECTORS[p.uuid] for p in pages}


def _build_field(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    (tmp_path / "rotate.md").write_text(PAGE_ROTATE)
    (tmp_path / "rotate-old.md").write_text(PAGE_ROTATE_OLD)
    (tmp_path / "rotate-new.md").write_text(PAGE_ROTATE_NEW)
    (tmp_path / "billing.md").write_text(PAGE_BILLING)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    return conn


def _agree_with(uuid: str):
    def _fake_embed_query(query, model_kind, model_name):
        return _PAGE_VECTORS[uuid]
    return _fake_embed_query


def test_search_finds_fts_matches(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(search, "_embed_query", _agree_with("page-rotate"))

    result = search.search(conn, "rotate signing key", limit=5)
    uuids = [r.uuid for r in result.results]
    assert "page-rotate" in uuids
    assert "page-rotate-new" in uuids
    conn.close()


def test_confidence_high_when_fts_and_dense_agree(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(search, "confidence", _low_floor_confidence)
    # "rotate signing key" ranks page-rotate/page-rotate-new near the
    # top on FTS; make dense agree with whichever FTS puts first.
    fts_ranked, _ = search._fts_search(conn, "rotate signing key", 5)
    top_fts_uuid = fts_ranked[0][0]
    monkeypatch.setattr(search, "_embed_query", _agree_with(top_fts_uuid))

    result = search.search(conn, "rotate signing key", limit=5)
    assert result.confidence == "high"
    conn.close()


def test_confidence_low_when_fts_and_dense_disagree(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(search, "confidence", _low_floor_confidence)
    fts_ranked, _ = search._fts_search(conn, "rotate signing key", 5)
    top_fts_uuid = fts_ranked[0][0]
    other_uuid = next(u for u in _PAGE_VECTORS if u != top_fts_uuid)
    monkeypatch.setattr(search, "_embed_query", _agree_with(other_uuid))

    result = search.search(conn, "rotate signing key", limit=5)
    assert result.confidence == "low"
    conn.close()


def test_no_fts_hit_still_ranks_by_dense(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(search, "_embed_query", _agree_with("page-billing"))

    # Stopwords-only query: fts_query() returns an empty expression, so
    # there's no FTS hit at all. Dense still ranks; the fake query
    # vector is exactly page-billing's (distance 0), so the dense floor
    # passes and the gate says low (a lead), not none.
    result = search.search(conn, "is the a of", limit=5)
    assert result.results[0].uuid == "page-billing"
    assert result.confidence == "low"
    conn.close()


def test_no_fts_hit_and_far_dense_is_none(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    far = [0.0] * EMBEDDING_DIM
    far[EMBEDDING_DIM - 1] = 1.0  # orthogonal to every page vector
    monkeypatch.setattr(search, "_embed_query", lambda q, k, n: far)

    result = search.search(conn, "is the a of", limit=5)
    assert result.confidence == "none"
    assert result.results  # best-effort candidates still returned
    conn.close()


def test_ranking_is_dense_first(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    # FTS would rank the rotate pages first for this query; dense says
    # billing. Dense wins the presented order (ROADMAP.md 2.6).
    monkeypatch.setattr(search, "_embed_query", _agree_with("page-billing"))
    result = search.search(conn, "rotate signing key", limit=5)
    assert result.results[0].uuid == "page-billing"
    conn.close()


def test_superseded_page_folds_to_pointer(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(search, "_embed_query", _agree_with("page-rotate-new"))

    result = search.search(conn, "rotate keys old process", limit=5)
    old_stub = next(r for r in result.results if r.uuid == "page-rotate-old")
    assert old_stub.superseded_by == "page-rotate-new"
    assert old_stub.title == ""  # folded, not a full stub
    conn.close()


def test_neighbors_include_typed_links(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(search, "_embed_query", _agree_with("page-rotate-new"))

    result = search.search(conn, "rotate signing key current", limit=5)
    new_stub = next(r for r in result.results if r.uuid == "page-rotate-new")
    neighbor_uuids = [n.uuid for n in new_stub.neighbors]
    assert "page-rotate-old" in neighbor_uuids
    conn.close()


def test_budget_drops_neighbors_before_dropping_stubs(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(search, "_embed_query", _agree_with("page-rotate"))

    unbudgeted = search.search(conn, "rotate signing key", limit=5)
    assert any(r.neighbors for r in unbudgeted.results)

    stub_cost = search._stub_cost(unbudgeted.results[0])
    budgeted = search.search(conn, "rotate signing key", limit=5, budget=stub_cost + 2)
    assert len(budgeted.results) >= 1
    assert all(not r.neighbors for r in budgeted.results)
    conn.close()


def test_budget_zero_returns_no_results(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(search, "_embed_query", _agree_with("page-rotate"))

    result = search.search(conn, "rotate signing key", limit=5, budget=0)
    assert result.results == []
    conn.close()


def test_as_dict_roundtrips_confidence_and_results(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(search, "_embed_query", _agree_with("page-rotate"))

    result = search.search(conn, "rotate signing key", limit=2)
    d = result.as_dict()
    assert d["confidence"] == result.confidence
    assert len(d["results"]) == len(result.results)
    assert "uuid" in d["results"][0]
    conn.close()
