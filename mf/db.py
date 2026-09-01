"""Connection helpers for a memoryfield's `mf.sqlite3` index.

`mf.sqlite3` is derived and deletable (docs/architecture.md "Index"
layer) -- everything in it can be rebuilt from the pages on disk via
`mf index`. This module only opens connections and applies schema; it
doesn't decide what goes in the tables (see mf/indexer.py).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from . import schema

DB_FILENAME = "mf.sqlite3"


class FieldExistsError(FileExistsError):
    """Raised by init_field() when mf.sqlite3 already exists."""


class FieldNotFoundError(FileNotFoundError):
    """Raised when a command needs mf.sqlite3 but it doesn't exist."""


class SchemaVersionError(RuntimeError):
    """Raised by open_field() when mf.sqlite3 was built by a different
    schema version. There is no in-place migration: vec0 tables can't
    change distance metric, and the index is rebuildable anyway.
    """


def connect(db_path: Path) -> sqlite3.Connection:
    """Open `db_path` with sqlite-vec loaded and foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def init_field(
    field_dir: Path,
    model_code: str = schema.DEFAULT_MODEL_CODE,
    embedding_dim: int = schema.EMBEDDING_DIM,
) -> Path:
    """Create `mf.sqlite3` in `field_dir`. Raises FieldExistsError if
    one is already there -- `mf init` never silently reinitializes an
    existing field, since that would orphan its config/model_code
    without a matching re-embed.
    """
    db_path = field_dir / DB_FILENAME
    if db_path.exists():
        raise FieldExistsError(str(db_path))
    conn = connect(db_path)
    try:
        schema.apply_schema(conn, embedding_dim=embedding_dim)
        schema.set_config(conn, "model_code", model_code)
        schema.set_config(conn, "embedding_dim", str(embedding_dim))
        schema.set_config(conn, "schema_version", str(schema.SCHEMA_VERSION))
        conn.commit()
    finally:
        conn.close()
    return db_path


def open_field(field_dir: Path) -> sqlite3.Connection:
    """Open an existing field's mf.sqlite3. Raises FieldNotFoundError
    if `mf init` hasn't been run here yet.
    """
    db_path = field_dir / DB_FILENAME
    if not db_path.exists():
        raise FieldNotFoundError(
            f"{db_path} not found; run `mf init` in {field_dir} first"
        )
    conn = connect(db_path)
    version = schema.get_config(conn, "schema_version")
    if version != str(schema.SCHEMA_VERSION):
        conn.close()
        raise SchemaVersionError(
            f"{db_path} is schema v{version or '?'}, this mf needs "
            f"v{schema.SCHEMA_VERSION}. The index is derived: delete "
            f"{DB_FILENAME}, then run `mf init` and `mf index` in {field_dir}. "
            "Note: the reads log and co_read weights are not derived and "
            "will be lost (docs/architecture.md, Index layer)."
        )
    return conn
