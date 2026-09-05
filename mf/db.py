"""Connection helpers for a memoryfield's `mf.sqlite3` index.

`mf.sqlite3` is derived and deletable (docs/architecture.md "Index"
layer) -- everything in it can be rebuilt from the pages on disk via
`mf index`, except the read log, `co_read` weights, and claims, which
`migrate_field()` preserves across schema bumps. This module only opens
connections and applies schema; it doesn't decide what goes in the
tables (see mf/indexer.py).

WAL journal mode plus a 30-second busy timeout: more than one process
touches a field at once by design (two Claude Code sessions, CLAUDE.md
gotcha 24; Stop/SessionEnd hooks; the MCP server's worker threads).
Under the default rollback journal a running `mf index` blocked every
reader for its whole walk, and the default 5-second timeout then turned
that into `database is locked`. WAL lets readers proceed during a write.
The cost is `mf.sqlite3-wal`/`-shm` sidecars next to the index, which
`mf pack` handles by copying through the backup API rather than reading
the file (docs/architecture.md, Index layer).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from . import schema
from .embedder import registry_entry

DB_FILENAME = "mf.sqlite3"
# Where `mf init` puts a field when no directory is given, and where
# every other command looks when the cwd itself is not a field.
DEFAULT_FIELD_DIRNAME = "notes"


def resolve_field_dir(value: str | None, cwd: Path | None = None) -> Path:
    """The field a command should use when `--field`/DIR was left at its
    default. The cwd wins if it is a field, then `cwd/notes` if that
    is one, else the cwd (so the error names the directory the user is
    in). An explicit value is resolved as given, no guessing."""
    base = (cwd or Path.cwd()).resolve()
    if value is not None:
        return (base / value).resolve()
    if (base / DB_FILENAME).exists():
        return base
    candidate = base / DEFAULT_FIELD_DIRNAME
    if (candidate / DB_FILENAME).exists():
        return candidate
    return base
BUSY_TIMEOUT_S = 30


class FieldExistsError(FileExistsError):
    """Raised by init_field() when mf.sqlite3 already exists."""


class FieldNotFoundError(FileNotFoundError):
    """Raised when a command needs mf.sqlite3 but it doesn't exist."""


class SchemaVersionError(RuntimeError):
    """Raised by open_field() when mf.sqlite3 was built by a different
    schema version, or isn't an mf index at all. v2 migrates in place via
    `mf index`; older versions are rebuilt (`mf init` + `mf index`).
    """


def connect(db_path: Path) -> sqlite3.Connection:
    """Open `db_path` with sqlite-vec loaded, foreign keys on, WAL mode."""
    conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_S)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
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
    without a matching re-embed. A failure part-way removes the file so
    the next `mf init` doesn't report a field that was never built.
    """
    registry_dim = registry_entry(model_code)["dim"]
    if registry_dim != embedding_dim:
        raise ValueError(
            f"model {model_code!r} produces {registry_dim}-d vectors, not {embedding_dim}"
        )
    field_dir.mkdir(parents=True, exist_ok=True)
    db_path = field_dir / DB_FILENAME
    if db_path.exists():
        raise FieldExistsError(str(db_path))
    conn = None
    try:
        conn = connect(db_path)
        schema.apply_schema(conn, embedding_dim=embedding_dim)
        schema.set_config(conn, "model_code", model_code)
        schema.set_config(conn, "embedding_dim", str(embedding_dim))
        schema.set_config(conn, "schema_version", str(schema.SCHEMA_VERSION))
        conn.commit()
    except BaseException:
        if conn is not None:
            conn.close()
        for suffix in ("", "-wal", "-shm", "-journal"):
            Path(str(db_path) + suffix).unlink(missing_ok=True)
        raise
    conn.close()
    return db_path


def _version_message(db_path: Path, version: str | None) -> str:
    field_dir = db_path.parent
    if version and version.isdigit() and int(version) in schema.MIGRATABLE_VERSIONS:
        return (
            f"{db_path} is schema v{version}, this mf needs v{schema.SCHEMA_VERSION}. "
            f"Run `mf index` in {field_dir} to migrate it in place (the reads log, "
            "co_read weights, and claims are kept)."
        )
    return (
        f"{db_path} is schema v{version or '?'}, this mf needs "
        f"v{schema.SCHEMA_VERSION}. The index is derived: delete "
        f"{DB_FILENAME}, then run `mf init` and `mf index` in {field_dir}. "
        "Note: the reads log and co_read weights are not derived and "
        "will be lost (docs/architecture.md, Index layer)."
    )


def _connect_index(db_path: Path) -> sqlite3.Connection:
    """connect(), with "not a SQLite file at all" turned into the same
    SchemaVersionError a missing config table gets."""
    try:
        return connect(db_path)
    except sqlite3.DatabaseError as e:
        raise SchemaVersionError(
            f"{db_path} is not an mf index ({e}); delete it, then run `mf init` "
            f"and `mf index` in {db_path.parent}"
        ) from e


def _read_version(conn: sqlite3.Connection, db_path: Path) -> str | None:
    try:
        return schema.get_config(conn, "schema_version")
    except sqlite3.DatabaseError as e:
        # No `config` table, or not a SQLite file at all.
        conn.close()
        raise SchemaVersionError(
            f"{db_path} is not an mf index ({e}); delete it, then run `mf init` "
            f"and `mf index` in {db_path.parent}"
        ) from e


def open_field(field_dir: Path) -> sqlite3.Connection:
    """Open an existing field's mf.sqlite3. Raises FieldNotFoundError
    if `mf init` hasn't been run here yet, SchemaVersionError if the
    index is another version (see `migrate_field`) or not an index.
    """
    db_path = field_dir / DB_FILENAME
    if not db_path.exists():
        raise FieldNotFoundError(
            f"{db_path} not found; run `mf init` in {field_dir} first"
        )
    conn = _connect_index(db_path)
    version = _read_version(conn, db_path)
    if version != str(schema.SCHEMA_VERSION):
        conn.close()
        raise SchemaVersionError(_version_message(db_path, version))
    return conn


def migrate_field(field_dir: Path) -> int | None:
    """Migrate a `MIGRATABLE_VERSIONS` index in place. Returns the version
    it came from, or None when nothing needed doing. Only `mf index`
    calls this: the derived tables it drops are exactly what `index`
    rebuilds next, so the field is never left half-migrated for another
    command to trip over.
    """
    db_path = field_dir / DB_FILENAME
    if not db_path.exists():
        raise FieldNotFoundError(
            f"{db_path} not found; run `mf init` in {field_dir} first"
        )
    conn = _connect_index(db_path)
    try:
        version = _read_version(conn, db_path)
        if version == str(schema.SCHEMA_VERSION):
            return None
        if not (version and version.isdigit() and int(version) in schema.MIGRATABLE_VERSIONS):
            raise SchemaVersionError(_version_message(db_path, version))
        schema.migrate(conn, int(version))
        return int(version)
    finally:
        conn.close()
