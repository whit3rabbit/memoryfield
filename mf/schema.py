"""SQLite schema for a memoryfield's index (`mf.sqlite3`).

Tables per docs/architecture.md's "Index (derived, deletable)" layer.
The index is entirely rebuildable from the pages on disk via `mf index`;
nothing here is a source of truth for anything but retrieval and
provenance metadata.
"""
from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

# nomic-embed-text-v1.5's native output dimension. See mf/embedding.py
# and PLAN.md's embedder table.
EMBEDDING_DIM = 768
DEFAULT_MODEL_CODE = "nomic-embed-text-v1.5"

_DDL = """
CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    uuid      TEXT PRIMARY KEY,
    filename  TEXT NOT NULL,
    title     TEXT NOT NULL,
    summary   TEXT NOT NULL DEFAULT '',
    status    TEXT NOT NULL DEFAULT 'active',
    tokens    INTEGER NOT NULL DEFAULT 0,
    sha256    TEXT NOT NULL,
    updated   TEXT,
    writer    TEXT
);

CREATE TABLE IF NOT EXISTS sections (
    uuid       TEXT NOT NULL REFERENCES pages(uuid) ON DELETE CASCADE,
    slug       TEXT NOT NULL,
    ordinal    INTEGER NOT NULL,
    byte_start INTEGER NOT NULL,
    byte_end   INTEGER NOT NULL,
    tokens     INTEGER NOT NULL,
    PRIMARY KEY (uuid, slug)
);

CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    uuid UNINDEXED, title, summary, body,
    tokenize = 'porter ascii'
);

CREATE TABLE IF NOT EXISTS links (
    src    TEXT NOT NULL,
    dst    TEXT NOT NULL,
    kind   TEXT NOT NULL,  -- supersedes | contradicts | depends_on | co_read
    weight REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (src, dst, kind)
);

CREATE TABLE IF NOT EXISTS claims (
    slug       TEXT PRIMARY KEY,
    claimed_by TEXT NOT NULL,
    claimed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reads (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid    TEXT NOT NULL,
    section TEXT,
    tier    TEXT,
    read_at TEXT NOT NULL
);
"""

_VEC_DDL_TEMPLATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS vec USING vec0(
    page_uuid TEXT PRIMARY KEY,
    embedding FLOAT[{dim}]
);
"""


def apply_schema(conn: sqlite3.Connection, embedding_dim: int = EMBEDDING_DIM) -> None:
    """Create every table if it doesn't already exist. Idempotent."""
    conn.executescript(_DDL)
    conn.executescript(_VEC_DDL_TEMPLATE.format(dim=embedding_dim))
    conn.commit()


def get_config(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
