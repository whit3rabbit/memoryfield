import sqlite3

import sqlite_vec

from mf import schema


def _connect_memory() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def test_apply_schema_creates_every_table():
    conn = _connect_memory()
    schema.apply_schema(conn)
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        )
    }
    for table in ("config", "pages", "sections", "fts", "links", "claims", "vec", "reads"):
        assert table in names, f"missing table: {table}"


def test_apply_schema_is_idempotent():
    conn = _connect_memory()
    schema.apply_schema(conn)
    schema.apply_schema(conn)  # must not raise


def test_config_round_trip():
    conn = _connect_memory()
    schema.apply_schema(conn)
    assert schema.get_config(conn, "model_code") is None
    schema.set_config(conn, "model_code", "nomic-embed-text-v1.5")
    assert schema.get_config(conn, "model_code") == "nomic-embed-text-v1.5"
    schema.set_config(conn, "model_code", "updated-value")
    assert schema.get_config(conn, "model_code") == "updated-value"
