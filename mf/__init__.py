"""mf — the memoryfield CLI.

`mf.cli` is the entry point; every subcommand is a module here
(`mf/<verb>.py`) with a dataclass result and an `.as_dict()`. See
docs/CLI.md for the command reference and docs/architecture.md for the
schema and retrieval design.
"""
from __future__ import annotations

__version__ = "0.2.0"
