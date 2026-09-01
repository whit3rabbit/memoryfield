"""Command-line entry point for `mf`.

`init`/`index`/`search`/`read`/`write`/`raw add` are real (ROADMAP.md
1.3-1.6, 2.1-2.2). `lint`/`pack`/`unpack` (rest of Phase 2) aren't
built yet.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mf import __version__, db, indexer
from mf import raw as raw_mod
from mf import read as read_mod
from mf import search as search_mod
from mf import write as write_mod
from mf.page import PageParseError

STUB_COMMANDS = ()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mf", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mf {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="create mf.sqlite3 in a field")
    init_parser.add_argument("dir", nargs="?", default=".", help="field directory (default: cwd)")

    index_parser = subparsers.add_parser("index", help="scan a field's pages into mf.sqlite3")
    index_parser.add_argument("dir", nargs="?", default=".", help="field directory (default: cwd)")

    search_parser = subparsers.add_parser("search", help="search a field")
    search_parser.add_argument("query", help="the search query text")
    search_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    search_parser.add_argument("--limit", type=int, default=search_mod.DEFAULT_LIMIT)
    search_parser.add_argument(
        "--neighbor-limit", type=int, default=search_mod.DEFAULT_NEIGHBOR_LIMIT
    )
    search_parser.add_argument("--budget", type=int, default=None, help="token cap on the result set")
    search_parser.add_argument(
        "--stale-ok", action="store_true",
        help="return results whose page changed on disk since `mf index` (marked stale) instead of refusing",
    )
    search_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    read_parser = subparsers.add_parser("read", help="read a page's L1/L2 slice or a #section")
    read_parser.add_argument("refs", nargs="+", help="uuid or uuid#section, one or more")
    read_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    read_parser.add_argument("--tier", choices=read_mod.TIERS, default=None)
    read_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    write_parser = subparsers.add_parser("write", help="validate, dedup-check, and index a page")
    write_parser.add_argument(
        "path",
        help="draft page: a path outside the field (copied in on a pass), a path "
             "inside it (indexed in place), or '-' for stdin (needs --dest)",
    )
    write_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    write_parser.add_argument(
        "--dest", metavar="NAME", default=None,
        help="filename inside the field to write the draft to (default: the draft's own name)",
    )
    write_parser.add_argument(
        "--update", metavar="UUID", default=None,
        help="uuid this write intentionally updates (skips the dedup gate)",
    )
    write_parser.add_argument("--force", action="store_true", help="skip the dedup gate")
    write_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    raw_parser = subparsers.add_parser("raw", help="raw/ staging-area operations")
    raw_subparsers = raw_parser.add_subparsers(dest="raw_command")
    raw_add_parser = raw_subparsers.add_parser("add", help="append a session extract to raw/")
    raw_add_parser.add_argument(
        "text", nargs="?", default=None, help="text to append; reads stdin if omitted"
    )
    raw_add_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    raw_add_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    for name in STUB_COMMANDS:
        subparsers.add_parser(name)
    return parser


def _cmd_init(args: argparse.Namespace) -> int:
    field_dir = Path(args.dir).resolve()
    try:
        db_path = db.init_field(field_dir)
    except db.FieldExistsError as e:
        sys.stderr.write(f"mf init: {e} already exists; nothing to do.\n")
        return 1
    print(f"Initialized empty field at {db_path}")
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    field_dir = Path(args.dir).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf index: {e}\n")
        return 1
    try:
        result = indexer.index_field(field_dir, conn)
    finally:
        conn.close()
    print(
        f"{len(result.upserted)} upserted, {result.unchanged} unchanged, "
        f"{len(result.deleted)} deleted"
    )
    return 0


def _render_stub_text(stub: search_mod.Stub, indent: str = "") -> str:
    head = f"{indent}- [{stub.uuid}] {stub.title}"
    if stub.stale:
        head += " (stale)"
    lines = [head]
    if stub.summary:
        lines.append(f"{indent}    {stub.summary}")
    if stub.status != "active":
        lines.append(f"{indent}    status: {stub.status}")
    if stub.supersedes:
        lines.append(f"{indent}    supersedes: {', '.join(stub.supersedes)}")
    for neighbor in stub.neighbors:
        lines.append(_render_stub_text(neighbor, indent + "    "))
    return "\n".join(lines)


def _render_text(result: search_mod.SearchResult) -> str:
    lines = [f"confidence: {result.confidence}"]
    if not result.results:
        lines.append("(no results)")
    for stub in result.results:
        lines.append(_render_stub_text(stub))
    return "\n".join(lines)


def _cmd_search(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf search: {e}\n")
        return 1
    try:
        result = search_mod.search(
            conn, args.query, limit=args.limit,
            neighbor_limit=args.neighbor_limit, budget=args.budget,
            field_dir=field_dir, stale_ok=args.stale_ok,
        )
    except search_mod.StaleIndexError as e:
        sys.stderr.write(f"mf search: {e}\n")
        return 3
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(_render_text(result))
    return 0


def _render_read_text(results: list[read_mod.ReadResult]) -> str:
    lines = []
    for r in results:
        ref = f"{r.uuid}#{r.section}" if r.section else f"{r.uuid} ({r.tier})"
        lines.append(f"[{ref}] {r.title}")
        lines.append(r.body)
        if r is not results[-1]:
            lines.append("")
    return "\n".join(lines)


def _cmd_read(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf read: {e}\n")
        return 1
    try:
        results = read_mod.read(conn, args.refs, tier=args.tier, field_dir=field_dir)
    except (read_mod.PageNotFoundError, read_mod.SectionNotFoundError) as e:
        sys.stderr.write(f"mf read: not found: {e}\n")
        return 1
    finally:
        conn.close()

    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2))
    else:
        print(_render_read_text(results))
    return 0


def _render_write_text(result: write_mod.WriteResult) -> str:
    if result.written:
        return f"Wrote {result.uuid} to {result.path}"
    lines = [
        f"mf write: {len(result.duplicates)} possible near-duplicate(s) found; not written.",
    ]
    for d in result.duplicates:
        lines.append(f"  - [{d.uuid}] {d.title} (distance {d.distance:.3f})")
        lines.append(f"      {d.summary}")
    lines.append("Use --update <uuid> to update an existing page, or --force to write anyway.")
    if result.warning:
        lines.append(f"warning: {result.warning}")
    return "\n".join(lines)


def _cmd_write(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf write: {e}\n")
        return 1
    try:
        if args.path == "-":
            if not args.dest:
                sys.stderr.write("mf write: reading from stdin needs --dest NAME\n")
                return 1
            result = write_mod.write_text(
                field_dir, conn, sys.stdin.read(), args.dest,
                update_uuid=args.update, force=args.force,
            )
        else:
            result = write_mod.write_page(
                field_dir, conn, Path(args.path),
                update_uuid=args.update, force=args.force, dest_name=args.dest,
            )
    except (write_mod.WriteValidationError, PageParseError) as e:
        sys.stderr.write(f"mf write: {e}\n")
        return 1
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(_render_write_text(result))
    return 0 if result.written else 2


def _cmd_raw_add(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf raw add: {e}\n")
        return 1
    conn.close()  # raw/ never touches the index; only used to validate the field exists

    text = args.text if args.text is not None else sys.stdin.read()
    try:
        result = raw_mod.add_raw(field_dir, text)
    except raw_mod.EmptyRawTextError as e:
        sys.stderr.write(f"mf raw add: {e}\n")
        return 1

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    elif result.written:
        print(f"Appended to {result.path}")
    else:
        print(f"Skipped: duplicate of {result.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "init":
        return _cmd_init(args)
    if args.command == "index":
        return _cmd_index(args)
    if args.command == "search":
        return _cmd_search(args)
    if args.command == "read":
        return _cmd_read(args)
    if args.command == "write":
        return _cmd_write(args)
    if args.command == "raw":
        if args.raw_command == "add":
            return _cmd_raw_add(args)
        sys.stderr.write("mf raw: expected a subcommand (add)\n")
        return 1
    sys.stderr.write(
        f"mf {args.command}: not implemented yet — see ROADMAP.md Phase 1/2.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
