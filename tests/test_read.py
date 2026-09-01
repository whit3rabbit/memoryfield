from mf import db, indexer, read
from mf.schema import EMBEDDING_DIM

PAGE_ROTATE = """\
---
uuid: page-rotate
title: "How to rotate the signing key"
summary: "Run make rotate-key"
---

## Steps

Run `make rotate-key`.

## History

Rotated quarterly since 2023.
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

PAGE_SINGLE_SECTION = """\
---
uuid: page-single
title: "A page with only an L1"
summary: "No L2 content"
---

Just one block of text, no ## headings.
"""


def _fake_embed_pages(pages, model_code):
    return {p.uuid: [0.1] * EMBEDDING_DIM for p in pages}


def _build_field(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    (tmp_path / "rotate.md").write_text(PAGE_ROTATE)
    (tmp_path / "billing.md").write_text(PAGE_BILLING)
    (tmp_path / "single.md").write_text(PAGE_SINGLE_SECTION)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    return conn


def test_read_default_tier_returns_l1(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    results = read.read(conn, ["page-rotate"], field_dir=tmp_path)
    assert len(results) == 1
    r = results[0]
    assert r.tier == "L1"
    assert r.section is None
    assert "make rotate-key" in r.body
    assert "Rotated quarterly" not in r.body
    conn.close()


def test_read_l2_returns_everything_after_l1(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    r = read.read(conn, ["page-rotate"], tier="L2", field_dir=tmp_path)[0]
    assert r.tier == "L2"
    assert "Rotated quarterly" in r.body
    assert "make rotate-key" not in r.body
    conn.close()


def test_read_l2_on_single_section_page_is_empty(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    r = read.read(conn, ["page-single"], tier="L2", field_dir=tmp_path)[0]
    assert r.body == ""
    conn.close()


def test_read_named_section(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    r = read.read(conn, ["page-rotate#history"], field_dir=tmp_path)[0]
    assert r.section == "history"
    assert r.tier is None
    assert "Rotated quarterly" in r.body
    conn.close()


def test_read_unknown_uuid_raises(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    try:
        read.read(conn, ["does-not-exist"], field_dir=tmp_path)
        assert False, "expected PageNotFoundError"
    except read.PageNotFoundError:
        pass
    conn.close()


def test_read_unknown_section_raises(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    try:
        read.read(conn, ["page-rotate#nope"], field_dir=tmp_path)
        assert False, "expected SectionNotFoundError"
    except read.SectionNotFoundError:
        pass
    conn.close()


def test_read_logs_each_read(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    read.read(conn, ["page-rotate"], field_dir=tmp_path)
    read.read(conn, ["page-rotate#history"], field_dir=tmp_path)
    rows = conn.execute("SELECT uuid, section, tier FROM reads ORDER BY id").fetchall()
    assert rows == [("page-rotate", None, "L1"), ("page-rotate", "history", None)]
    conn.close()


def test_read_single_ref_does_not_bump_co_read(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    read.read(conn, ["page-rotate"], field_dir=tmp_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM links WHERE kind = 'co_read'"
    ).fetchone()[0]
    assert count == 0
    conn.close()


def test_read_multiple_refs_bumps_co_read_between_them(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    read.read(conn, ["page-rotate", "page-billing"], field_dir=tmp_path)
    row = conn.execute(
        "SELECT src, dst, weight FROM links WHERE kind = 'co_read'"
    ).fetchone()
    assert row == ("page-billing", "page-rotate", 1.0)
    conn.close()


def test_read_co_read_weight_accumulates_across_calls(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    read.read(conn, ["page-rotate", "page-billing"], field_dir=tmp_path)
    read.read(conn, ["page-billing", "page-rotate"], field_dir=tmp_path)
    row = conn.execute(
        "SELECT weight FROM links WHERE kind = 'co_read'"
    ).fetchone()
    assert row[0] == 2.0
    conn.close()


def test_read_failure_does_not_log_partial_reads(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    try:
        read.read(conn, ["page-rotate", "does-not-exist"], field_dir=tmp_path)
    except read.PageNotFoundError:
        pass
    count = conn.execute("SELECT COUNT(*) FROM reads").fetchone()[0]
    assert count == 0
    conn.close()


def test_as_dict_omits_unset_section_or_tier(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    tier_result = read.read(conn, ["page-rotate"], field_dir=tmp_path)[0]
    section_result = read.read(conn, ["page-rotate#history"], field_dir=tmp_path)[0]
    assert "section" not in tier_result.as_dict()
    assert "tier" in tier_result.as_dict()
    assert "tier" not in section_result.as_dict()
    assert "section" in section_result.as_dict()
    conn.close()


def test_read_works_after_the_field_directory_moves(tmp_path, monkeypatch):
    """pages.filename is field-relative, so a copied or moved field (a
    clone, a pack/unpack round trip) still resolves pages by uuid.
    """
    import shutil

    field = tmp_path / "field"
    field.mkdir()
    conn = _build_field(field, monkeypatch)
    conn.close()

    moved = tmp_path / "moved"
    shutil.copytree(field, moved)
    shutil.rmtree(field)

    conn = db.open_field(moved)
    r = read.read(conn, ["page-rotate"], field_dir=moved)[0]
    assert "make rotate-key" in r.body
    conn.close()
