"""Round trip against a real spec archive (ROADMAP.md 2.4's unverified
half): Cal Paterson's soapstones export, 95 pages written by many agents
with none of this project's writing discipline, plus a spec
`nomic-embed-text-v1.5.sqlite3` index mf does not read.

The fixture is fetched, not committed (`uv run python3
eval/fetch_soapstones.py`; content license unstated, sha256 pinned).
Absent fixture: skipped, not failed.
"""
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from mf import db, indexer, lint, pack, search
from mf.schema import EMBEDDING_DIM

FIXTURE = Path(__file__).resolve().parent.parent / "eval" / "fixtures" / "soapstones.memoryfield.zip"
PAGES = 95  # 94 soapstones + index.md, which carries frontmatter and is a page

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="fixture missing; run `uv run python3 eval/fetch_soapstones.py`"
)


def _fake_embed(pages, model_code):
    return {p.uuid: [0.1] * EMBEDDING_DIM for p in pages}


def _fake_embed_texts(texts, model_code):
    return [[0.5] * EMBEDDING_DIM for _ in texts]


@pytest.fixture
def field(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed)
    dest = tmp_path / "soap"
    unpacked = pack.unpack_field(FIXTURE, dest)
    db.init_field(dest)
    conn = db.open_field(dest)
    indexed = indexer.index_field(dest, conn)
    yield dest, conn, unpacked, indexed
    conn.close()


def test_spec_archive_unpacks_as_is_and_indexes_every_page(field):
    dest, conn, unpacked, indexed = field
    assert unpacked.verified is None and unpacked.stripped_prefix == ""  # flat, no sidecar
    assert unpacked.has_index is False
    assert any("nomic-embed-text-v1.5.sqlite3" in n and "mf init" in n for n in unpacked.notes)
    assert len(list(dest.glob("*.md"))) == PAGES
    assert len(indexed.upserted) == PAGES
    assert conn.execute("SELECT count(*) FROM pages").fetchone()[0] == PAGES


def test_lint_reads_the_field_and_flags_its_title_summaries(field):
    dest, conn, _, _ = field
    r = lint.lint_field(dest, conn)
    assert r.pages == PAGES and r.count("error") == 0
    codes = [f.code for f in r.findings]
    # 74/95 summaries are a copied H1 (`# Title`); the spec checks pass.
    assert codes.count("summary-shape") >= 70
    for code in ("spec-yaml", "spec-filename", "spec-subdir", "spec-dates"):
        assert code not in codes, code
    assert "invalid-page" not in codes


def test_search_returns_stubs_from_a_foreign_field(field, monkeypatch):
    dest, conn, _, _ = field
    monkeypatch.setattr(search, "_embed_query", lambda q, m: [0.1] * EMBEDDING_DIM)
    r = search.search(conn, "search reddit without auth", limit=2, field_dir=dest)
    assert 1 <= len(r.results) <= 2
    assert all(s.title for s in r.results)


def test_pack_spec_round_trips_the_foreign_field(field, tmp_path, monkeypatch):
    dest, conn, _, _ = field
    conn.close()
    monkeypatch.setattr(pack, "_embed_texts", _fake_embed_texts)
    r = pack.pack_field(dest, out=tmp_path / "again.memoryfield.zip", spec=True)
    names = zipfile.ZipFile(r.path).namelist()
    assert sum(n.endswith(".md") for n in names) == PAGES
    assert r.spec_index == "snowflake-arctic-embed-xs.sqlite3" and r.spec_index in names
    assert "mf.sqlite3" not in names and "nomic-embed-text-v1.5.sqlite3" not in names
    assert r.skipped == []
    idx = tmp_path / "idx.sqlite3"
    idx.write_bytes(zipfile.ZipFile(r.path).read(r.spec_index))
    c = sqlite3.connect(idx)
    n, emb, fm = c.execute("SELECT count(*), length(embedding), frontmatter FROM pages").fetchone()
    c.close()
    assert n == PAGES and emb == EMBEDDING_DIM * 4
    assert set(json.loads(fm)) >= {"title", "uuid", "created", "updated", "summary"}
