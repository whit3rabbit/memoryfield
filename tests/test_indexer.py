from mf import db, indexer

PAGE_1 = """\
---
uuid: page-001
title: "Rotate the key"
summary: "Run make rotate-key"
supersedes: [page-000]
---

## Steps

Run `make rotate-key`.

## Rationale

Limits blast radius.
"""

NOT_A_PAGE = "# Just a readme\n\nNo frontmatter.\n"


def _fake_embed_pages(pages, model_code):
    """Deterministic stand-in for indexer._embed_pages, avoids loading
    a real fastembed model in tests (slow, network/cache dependent).
    Dimension must match schema.EMBEDDING_DIM (the vec0 table's fixed
    width) or sqlite-vec rejects the insert.
    """
    from mf.schema import EMBEDDING_DIM
    return {p.uuid: [0.1] * EMBEDDING_DIM for p in pages}


def _write(tmp_path, name, text):
    (tmp_path / name).write_text(text)


def test_discover_pages_skips_files_without_frontmatter(tmp_path):
    _write(tmp_path, "page1.md", PAGE_1)
    _write(tmp_path, "readme.md", NOT_A_PAGE)
    pages = indexer.discover_pages(tmp_path)
    assert list(pages) == ["page-001"]


def test_discover_pages_skips_dotdirs_and_skip_dirs(tmp_path):
    _write(tmp_path, "page1.md", PAGE_1)
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "fake.md").write_text(PAGE_1.replace("page-001", "page-999"))
    pages = indexer.discover_pages(tmp_path)
    assert list(pages) == ["page-001"]


def test_index_field_upserts_new_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    _write(tmp_path, "page1.md", PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)

    result = indexer.index_field(tmp_path, conn)
    assert result.upserted == ["page-001"]
    assert result.unchanged == 0

    row = conn.execute("SELECT title, summary FROM pages WHERE uuid = ?", ("page-001",)).fetchone()
    assert row == ("Rotate the key", "Run make rotate-key")

    sections = conn.execute(
        "SELECT slug FROM sections WHERE uuid = ? ORDER BY ordinal", ("page-001",)
    ).fetchall()
    assert sections == [("steps",), ("rationale",)]

    fts_hit = conn.execute("SELECT uuid FROM fts WHERE fts MATCH 'rotate'").fetchall()
    assert fts_hit == [("page-001",)]

    vec_hit = conn.execute("SELECT page_uuid FROM vec").fetchall()
    assert vec_hit == [("page-001",)]

    links = conn.execute("SELECT src, dst, kind FROM links").fetchall()
    assert links == [("page-001", "page-000", "supersedes")]
    conn.close()


def test_index_field_is_incremental(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    _write(tmp_path, "page1.md", PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)

    indexer.index_field(tmp_path, conn)
    result = indexer.index_field(tmp_path, conn)
    assert result.upserted == []
    assert result.unchanged == 1
    conn.close()


def test_index_field_removes_deleted_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    page_path = tmp_path / "page1.md"
    page_path.write_text(PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)

    page_path.unlink()
    result = indexer.index_field(tmp_path, conn)
    assert result.deleted == ["page-001"]

    for table, column in (("pages", "uuid"), ("sections", "uuid"), ("links", "src")):
        rows = conn.execute(f"SELECT {column} FROM {table}").fetchall()
        assert rows == [], f"{table} still has rows after deletion"
    assert conn.execute("SELECT uuid FROM fts").fetchall() == []
    assert conn.execute("SELECT page_uuid FROM vec").fetchall() == []
    conn.close()


def test_index_field_reembeds_on_content_change(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    page_path = tmp_path / "page1.md"
    page_path.write_text(PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)

    page_path.write_text(PAGE_1 + "\n## New Section\n\nMore content.\n")
    result = indexer.index_field(tmp_path, conn)
    assert result.upserted == ["page-001"]

    sections = conn.execute(
        "SELECT slug FROM sections WHERE uuid = ? ORDER BY ordinal", ("page-001",)
    ).fetchall()
    assert sections == [("steps",), ("rationale",), ("new-section",)]
    conn.close()
