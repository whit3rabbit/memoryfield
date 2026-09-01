"""Command-line entry point for `mf`.

`init`/`index`/`search`/`read` are real (ROADMAP.md 1.3-1.6). `write`
(Phase 2) is still a stub.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mf import __version__, db, indexer
from mf import read as read_mod
from mf import search as search_mod

STUB_COMMANDS = ("write",)


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
    search_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    read_parser = subparsers.add_parser("read", help="read a page's L1/L2 slice or a #section")
    read_parser.add_argument("refs", nargs="+", help="uuid or uuid#section, one or more")
    read_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    read_parser.add_argument("--tier", choices=read_mod.TIERS, default=None)
    read_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

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
    except db.FieldNotFoundError as e:
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
    if stub.superseded_by:
        return f"{indent}- [{stub.uuid}] -> superseded_by {stub.superseded_by}"
    lines = [f"{indent}- [{stub.uuid}] {stub.title}"]
    if stub.summary:
        lines.append(f"{indent}    {stub.summary}")
    if stub.status != "active":
        lines.append(f"{indent}    status: {stub.status}")
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
    except db.FieldNotFoundError as e:
        sys.stderr.write(f"mf search: {e}\n")
        return 1
    try:
        result = search_mod.search(
            conn, args.query, limit=args.limit,
            neighbor_limit=args.neighbor_limit, budget=args.budget,
        )
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
    except db.FieldNotFoundError as e:
        sys.stderr.write(f"mf read: {e}\n")
        return 1
    try:
        results = read_mod.read(conn, args.refs, tier=args.tier)
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
    sys.stderr.write(
        f"mf {args.command}: not implemented yet — see ROADMAP.md Phase 1/2.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
