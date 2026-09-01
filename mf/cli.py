"""Command-line entry point for `mf`.

Subcommands are stubs until their ROADMAP.md phase lands: `init`/`index`/
`search`/`read` in Phase 1 (M1), `write` in Phase 2 (M2).
"""
from __future__ import annotations

import argparse
import sys

from mf import __version__

COMMANDS = ("init", "index", "search", "read", "write")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mf", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mf {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    for name in COMMANDS:
        subparsers.add_parser(name)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    sys.stderr.write(
        f"mf {args.command}: not implemented yet — see ROADMAP.md Phase 1/2.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
