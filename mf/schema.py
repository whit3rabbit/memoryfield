"""SQLite schema for a memoryfield's index (`mf.sqlite3`).

Tables per docs/architecture.md's "Index (derived, deletable)" layer.
Everything here except `config`, `claims`, `reads`, and the `co_read`
rows of `links` is rebuildable from the pages on disk via `mf index`;
those four accumulate from tool calls and have no other source (CLAUDE.md
gotcha 33), which is why `migrate()` below keeps them.
"""
from __future__ import annotations

import sqlite3

from .embedder import UnknownModelCodeError, registry_entry

# v2 (ROADMAP.md 2.5): `vec` uses cosine distance instead of vec0's
# default Euclidean L2, and `reads` gained `call_id`.
# v3: `fts` rows share `pages.rowid` so a page's FTS row can be deleted by
# rowid instead of a full virtual-table scan on the UNINDEXED uuid column;
# `sections` lost `byte_start`/`byte_end` (computed against a stripped
# body nothing persisted, and never read); indexes on `links(dst, kind)`
# and `reads`. A v2 index migrates in place (`migrate()`), a v1 index
# does not (vec0 tables can't change metric).
SCHEMA_VERSION = 3
MIGRATABLE_VERSIONS = (2,)

# snowflake-arctic-embed-xs's native output dimension (384-d). See mf/embedding.py,
# mf/embedder.py, and docs/BENCHMARKS.md.
EMBEDDING_DIM = 384
DEFAULT_MODEL_CODE = "snowflake-arctic-embed-xs"

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
CREATE INDEX IF NOT EXISTS links_dst ON links (dst, kind);

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
    read_at TEXT NOT NULL,
    call_id TEXT NOT NULL  -- one `mf read` invocation; co_read is rebuildable from rows sharing it
);
CREATE INDEX IF NOT EXISTS reads_uuid ON reads (uuid);
CREATE INDEX IF NOT EXISTS reads_call ON reads (call_id);
"""

# Cosine, not vec0's default L2: fastembed's nomic vectors are not
# unit-normalized (norm ~20, measured), so L2 distance mixed vector
# magnitude into every kNN order, agreement signal, and dedup threshold,
# while the eval harness that calibrated those numbers used cosine
# (CLAUDE.md gotcha 32). Cosine distance here is 1 - cos, range [0, 2].
_VEC_DDL_TEMPLATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS vec USING vec0(
    page_uuid TEXT PRIMARY KEY,
    embedding FLOAT[{dim}] distance_metric=cosine
);
"""

# Tables `migrate()` drops and `mf index` rebuilds. Everything else in the
# file is kept.
_DERIVED_TABLES = ("pages", "sections", "fts", "vec")


class EmbeddingDimMismatchError(RuntimeError):
    """`config.model_code`'s registry dimension is not the width `vec` was
    created with. Only `mf init` writes both, so this means a hand-edited
    config or an index built by a different mf."""


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


def field_model(conn: sqlite3.Connection) -> tuple[str, int]:
    """`(model_code, embedding_dim)` for this field, checked against the
    registry. Every embedding call site goes through this rather than
    reading `model_code` on its own, so an unknown model or a dimension
    that disagrees with the `vec` table fails with a named error before
    any vector is built, not as a sqlite-vec error mid-insert.
    """
    model_code = get_config(conn, "model_code") or DEFAULT_MODEL_CODE
    registry_dim = registry_entry(model_code)["dim"]  # raises UnknownModelCodeError
    stored = get_config(conn, "embedding_dim")
    dim = int(stored) if stored else registry_dim
    if dim != registry_dim:
        raise EmbeddingDimMismatchError(
            f"config says embedding_dim={dim} but model {model_code!r} produces "
            f"{registry_dim}-d vectors; the index was built for a different model"
        )
    return model_code, dim


def migrate(conn: sqlite3.Connection, from_version: int) -> None:
    """Bring a `MIGRATABLE_VERSIONS` index up to `SCHEMA_VERSION` in place.
    Drops only the derived tables (`mf index` rebuilds them) and the
    typed links (rebuilt from frontmatter). `config`, `claims`, `reads`,
    and `co_read` links survive.
    """
    if from_version not in MIGRATABLE_VERSIONS:
        raise ValueError(f"cannot migrate schema v{from_version}")
    _, dim = field_model(conn)
    for table in _DERIVED_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute("DELETE FROM links WHERE kind != 'co_read'")
    conn.commit()
    apply_schema(conn, embedding_dim=dim)
    set_config(conn, "schema_version", str(SCHEMA_VERSION))
    conn.commit()


__all__ = [
    "DEFAULT_MODEL_CODE", "EMBEDDING_DIM", "MIGRATABLE_VERSIONS", "SCHEMA_VERSION",
    "EmbeddingDimMismatchError", "UnknownModelCodeError",
    "apply_schema", "field_model", "get_config", "migrate", "set_config",
]
