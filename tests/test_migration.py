"""Schema v2 -> v3 in place (mf/schema.py migrate, mf/db.py migrate_field):
the derived tables are rebuilt, the non-derived ones survive."""
from __future__ import annotations

import sqlite3

import pytest

from mf import cli, db, indexer, schema

PAGE = "---\nuuid: p1\ntitle: \"T\"\nsummary: \"S\"\n---\n\n## Answer\n\nbody\n"


def _downgrade_to_v2(field):
    """A v3 index dressed as v2: the byte columns v2 had, version 2, and
    rows in every table migrate() must keep."""
    conn = db.connect(field / db.DB_FILENAME)
    conn.execute("ALTER TABLE sections ADD COLUMN byte_start INTEGER NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE sections ADD COLUMN byte_end INTEGER NOT NULL DEFAULT 0")
    conn.execute("INSERT INTO reads (uuid, section, tier, read_at, call_id) VALUES ('p1', NULL, 'L1', 't', 'c1')")
    conn.execute("INSERT INTO links VALUES ('p1', 'p2', 'co_read', 3.0)")
    conn.execute("INSERT INTO links VALUES ('p1', 'p0', 'supersedes', 1.0)")
    conn.execute("INSERT INTO claims VALUES ('slug', 'me', 't')")
    schema.set_config(conn, "schema_version", "2")
    conn.commit()
    conn.close()


def test_migrate_field_keeps_reads_co_read_and_claims(tmp_path, field_factory):
    field = field_factory({"p1.md": PAGE})
    _downgrade_to_v2(field)
    with pytest.raises(db.SchemaVersionError, match="mf index"):
        db.open_field(field)

    assert db.migrate_field(field) == 2
    assert db.migrate_field(field) is None  # idempotent

    conn = db.open_field(field)
    assert schema.get_config(conn, "schema_version") == "3"
    assert conn.execute("SELECT count(*) FROM reads").fetchone()[0] == 1
    assert conn.execute("SELECT weight FROM links WHERE kind = 'co_read'").fetchone()[0] == 3.0
    assert conn.execute("SELECT count(*) FROM links WHERE kind = 'supersedes'").fetchone()[0] == 0
    assert conn.execute("SELECT claimed_by FROM claims").fetchone()[0] == "me"
    assert conn.execute("SELECT count(*) FROM pages").fetchone()[0] == 0
    cols = {row[1] for row in conn.execute("PRAGMA table_info(sections)")}
    assert "byte_start" not in cols
    # `mf index` rebuilds the derived side.
    result = indexer.index_field(field, conn)
    assert result.upserted == ["p1"]
    conn.close()


def test_cli_index_migrates_and_says_so(field_factory, capsys):
    field = field_factory({"p1.md": PAGE})
    _downgrade_to_v2(field)
    assert cli.main(["index", str(field)]) == 0
    out = capsys.readouterr().out
    assert "migrated index v2 -> v3" in out and "1 upserted" in out


def test_open_field_refuses_unmigratable_version(tmp_path):
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    schema.set_config(conn, "schema_version", "1")
    conn.commit()
    conn.close()
    with pytest.raises(db.SchemaVersionError, match="delete"):
        db.migrate_field(tmp_path)


def test_open_field_on_foreign_sqlite_is_schema_error(tmp_path):
    other = sqlite3.connect(tmp_path / db.DB_FILENAME)
    other.execute("CREATE TABLE t (x)")
    other.commit()
    other.close()
    with pytest.raises(db.SchemaVersionError, match="not an mf index"):
        db.open_field(tmp_path)


def test_open_field_on_garbage_file_is_schema_error(tmp_path):
    (tmp_path / db.DB_FILENAME).write_bytes(b"not a database at all\n" * 20)
    with pytest.raises(db.SchemaVersionError):
        db.open_field(tmp_path)


def test_init_field_dim_must_match_model(tmp_path):
    with pytest.raises(ValueError, match="384-d"):
        db.init_field(tmp_path, model_code="snowflake-arctic-embed-xs", embedding_dim=768)
    assert not (tmp_path / db.DB_FILENAME).exists()


def test_init_field_creates_missing_dir_and_wal(tmp_path):
    field = tmp_path / "deep" / "field"
    db.init_field(field)
    conn = db.open_field(field)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


def test_field_model_detects_dimension_mismatch(tmp_path):
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    schema.set_config(conn, "embedding_dim", "768")
    conn.commit()
    with pytest.raises(schema.EmbeddingDimMismatchError):
        schema.field_model(conn)
    conn.close()
