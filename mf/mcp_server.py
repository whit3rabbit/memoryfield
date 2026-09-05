"""`mf mcp` — MCP server wrapping search/read/write/raw_add (ROADMAP.md 5.1).

Each tool is a thin wrapper around the same library functions the CLI
calls (mf/search.py, mf/read.py, mf/write.py, mf/raw.py) and returns
the same `.as_dict()` shape `mf <verb> --json` prints — one exception:
`read` returns a list of `ReadResult`, and MCP structured tool output
must be a JSON object, so it's wrapped here as `{"results": [...]}`
instead of the CLI's bare JSON array.

Every failure the model could act on reaches it as a `ToolError` (a
readable tool result), never as a server-level crash: bad arguments
(no field at that path, a stale schema, a page/section that doesn't
exist, a bad tier or limit, a draft that fails validation, an empty raw
extract, a stale result without stale_ok) and environment failures
alike (a locked index, an unknown model, an unreadable page). `write`'s
dedup gate is not an error in that sense — like the CLI, a blocked
write returns normally with `written: false` and the candidate list in
`duplicates`.

Every tool takes `field`, resolved against the server process's cwd.
When a call leaves it out, the server's own `--field` (default ".")
applies, so a project-level MCP entry can pin a subdirectory field
with `mf mcp --field notes` and the agent never has to know where the
field lives. One server process serves one embedding model: the SDK runs these
sync tools on worker threads, and mf's model cache serializes loading,
so two fields pinned to different models through one server would
load both models into one process (CLAUDE.md gotcha 4).
"""
# pyright: reportMissingImports=false
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from sqlite3 import Connection
from typing import Any, TypeVar

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import db
from . import raw as raw_mod
from . import read as read_mod
from . import search as search_mod
from . import write as write_mod

mcp = MCPServer("mf")

T = TypeVar("T")

# Set once by `main(field=...)` from `mf mcp --field`; a per-call `field`
# still wins. Module state rather than a closure so tests can pin it.
_DEFAULT_FIELD = "."


def set_default_field(field: str) -> None:
    global _DEFAULT_FIELD
    _DEFAULT_FIELD = str(Path(field).resolve())


def _open(field: str | None) -> tuple[Path, Connection]:
    field_dir = Path(field or _DEFAULT_FIELD).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        raise ToolError(str(e)) from e
    return field_dir, conn


def _guarded(fn: Callable[[], T]) -> T:
    """Run a library call, turning any failure into a ToolError."""
    try:
        return fn()
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"{type(e).__name__}: {e}") from e


@mcp.tool()
def search(
    query: str,
    field: str | None = None,
    limit: int = search_mod.DEFAULT_LIMIT,
    neighbor_limit: int = search_mod.DEFAULT_NEIGHBOR_LIMIT,
    budget: int | None = None,
    stale_ok: bool = False,
) -> dict[str, Any]:
    """Search a field. Check `confidence` (high/low/none) before citing
    a result — `none` means the gate didn't trust the match."""
    field_dir, conn = _open(field)

    def run() -> dict[str, Any]:
        try:
            result = search_mod.search(
                conn, query, limit=limit, neighbor_limit=neighbor_limit,
                budget=budget, field_dir=field_dir, stale_ok=stale_ok,
            )
        except search_mod.StaleIndexError as e:
            raise ToolError(f"{e}; pass stale_ok=true or run `mf index`") from e
        return result.as_dict()

    try:
        return _guarded(run)
    finally:
        conn.close()


@mcp.tool()
def read(refs: list[str], field: str | None = None, tier: str | None = None) -> dict[str, Any]:
    """Read one or more refs (uuid, or uuid#section) at tier L1|L2.
    A bare uuid with no tier defaults to L1. Batch related refs into one
    call so the co_read signal (used by search's neighbor ranking) fires."""
    if tier is not None and tier not in read_mod.TIERS:
        raise ToolError(f"tier must be one of {', '.join(read_mod.TIERS)}, not {tier!r}")
    field_dir, conn = _open(field)

    def run() -> dict[str, Any]:
        try:
            results = read_mod.read(conn, refs, tier=tier, field_dir=field_dir)
        except (read_mod.PageNotFoundError, read_mod.SectionNotFoundError) as e:
            raise ToolError(f"not found: {e}") from e
        return {"results": [r.as_dict() for r in results]}

    try:
        return _guarded(run)
    finally:
        conn.close()


@mcp.tool()
def write(
    text: str,
    dest: str,
    field: str | None = None,
    update: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Validate, dedup-gate, and index a draft page (full frontmatter +
    body text) under filename `dest` inside the field. `written: false`
    with a `duplicates` list means the dedup gate blocked it — pass the
    existing page's uuid as `update` to update it, or `force=true` to
    write anyway."""
    field_dir, conn = _open(field)
    try:
        return _guarded(
            lambda: write_mod.write_text(
                field_dir, conn, text, dest, update_uuid=update, force=force
            ).as_dict()
        )
    finally:
        conn.close()


@mcp.tool()
def raw_add(text: str, field: str | None = None) -> dict[str, Any]:
    """Append a session extract to raw/ for a later `mf consolidate --plan`
    pass, rather than writing a page directly. Duplicate of the most
    recent entry is a silent no-op (retried/racing hook, not new)."""
    field_dir, conn = _open(field)
    conn.close()  # raw/ never touches the index; only used to validate the field exists
    return _guarded(lambda: raw_mod.add_raw(field_dir, text).as_dict())


def main(field: str = ".") -> None:
    set_default_field(field)
    mcp.run(transport="stdio")
