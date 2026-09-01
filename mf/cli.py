"""Command-line entry point for `mf`.

`init`/`index` are real (ROADMAP.md 1.3). `search`/`read` (Phase 1) and
`write` (Phase 2) are still stubs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mf import __version__, db, indexer

STUB_COMMANDS = ("search", "read", "write")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mf", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mf {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="create mf.sqlite3 in a field")
    init_parser.add_argument("dir", nargs="?", default=".", help="field directory (default: cwd)")

    index_parser = subparsers.add_parser("index", help="scan a field's pages into mf.sqlite3")
    index_parser.add_argument("dir", nargs="?", default=".", help="field directory (default: cwd)")

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
    sys.stderr.write(
        f"mf {args.command}: not implemented yet — see ROADMAP.md Phase 1/2.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
