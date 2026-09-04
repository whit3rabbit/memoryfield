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


PAGE_2 = """\
---
uuid: page-002
title: "Billing retries"
summary: "Dunning levels 1-4"
---

## Steps

Failed payments increment dunning_level.
"""


def test_index_stores_field_relative_filenames(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    sub = tmp_path / "nested"
    sub.mkdir()
    _write(sub, "page1.md", PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)

    (filename,) = conn.execute("SELECT filename FROM pages WHERE uuid = 'page-001'").fetchone()
    assert filename == "nested/page1.md"
    conn.close()


def test_reindex_of_an_edited_page_keeps_co_read(tmp_path, monkeypatch):
    """Regression: _delete_page_rows used to drop every links row with the
    page as src, including co_read weight that only `mf read` can create.
    """
    from mf import read

    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    page1 = tmp_path / "page1.md"
    page1.write_text(PAGE_1)
    _write(tmp_path, "page2.md", PAGE_2)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    read.read(conn, ["page-001", "page-002"], field_dir=tmp_path)

    page1.write_text(PAGE_1 + "\n## Edited\n\nNew content.\n")
    result = indexer.index_field(tmp_path, conn)
    assert result.upserted == ["page-001"]

    rows = conn.execute(
        "SELECT src, dst, weight FROM links WHERE kind = 'co_read'"
    ).fetchall()
    assert rows == [("page-001", "page-002", 1.0)]
    # Typed links are still rebuilt from frontmatter on the same upsert.
    typed = conn.execute(
        "SELECT dst FROM links WHERE src = 'page-001' AND kind = 'supersedes'"
    ).fetchall()
    assert typed == [("page-000",)]

    page1.unlink()
    indexer.index_field(tmp_path, conn)
    assert conn.execute("SELECT * FROM links WHERE kind = 'co_read'").fetchall() == []
    conn.close()


# --- discovery robustness (2026-09-03 audit) ------------------------------

def test_duplicate_uuid_files_are_reported_and_neither_indexed(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    _write(tmp_path, "a.md", PAGE_1)
    _write(tmp_path, "b.md", PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    result = indexer.index_field(tmp_path, conn)
    assert result.upserted == [] and result.duplicates == {"page-001": ["a.md", "b.md"]}
    conn.close()


def test_duplicate_uuid_keeps_the_existing_row(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    _write(tmp_path, "a.md", PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    _write(tmp_path, "copy.md", PAGE_1)
    result = indexer.index_field(tmp_path, conn)
    assert result.deleted == [] and "page-001" in result.duplicates
    assert conn.execute("SELECT filename FROM pages").fetchone()[0] == "a.md"
    conn.close()


def test_non_utf8_and_debris_files_do_not_abort_the_walk(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    _write(tmp_path, "page1.md", PAGE_1)
    (tmp_path / "latin.md").write_bytes(b"---\nuuid: l\ntitle: caf\xe9\n---\nx\n")
    _write(tmp_path, "page1.sync-conflict-1.md", PAGE_1.replace("page-001", "page-dup"))
    found = indexer.discover(tmp_path)
    assert list(found.pages) == ["page-001"]
    assert "latin.md" in found.skipped and "not UTF-8" in found.skipped["latin.md"]


def test_renamed_page_updates_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    _write(tmp_path, "old.md", PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    (tmp_path / "old.md").rename(tmp_path / "new.md")
    result = indexer.index_field(tmp_path, conn)
    assert result.upserted == ["page-001"]
    assert conn.execute("SELECT filename FROM pages").fetchone()[0] == "new.md"
    conn.close()


def test_fts_row_follows_the_page_rowid(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    _write(tmp_path, "page1.md", PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    _write(tmp_path, "page1.md", PAGE_1 + "\nmore\n")
    indexer.index_field(tmp_path, conn)
    assert conn.execute("SELECT count(*) FROM fts").fetchone()[0] == 1
    (tmp_path / "page1.md").unlink()
    indexer.index_field(tmp_path, conn)
    assert conn.execute("SELECT count(*) FROM fts").fetchone()[0] == 0
    conn.close()


def test_index_page_accepts_preparsed_page_and_embedding(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(indexer, "_embed_pages", lambda pages, model_code: calls.append(1) or _fake_embed_pages(pages, model_code))
    _write(tmp_path, "page1.md", PAGE_1)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    from mf.page import load_page
    from mf.schema import EMBEDDING_DIM
    page = load_page(tmp_path / "page1.md", filename="page1.md")
    indexer.index_page(tmp_path, conn, tmp_path / "page1.md", page=page, embedding=[0.2] * EMBEDDING_DIM)
    assert calls == []
    assert conn.execute("SELECT count(*) FROM vec").fetchone()[0] == 1
    conn.close()
