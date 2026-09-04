"""What docs/upstream/SPEC.md says every reader must agree on, in one place.

Three things used to live in two or three copies each: the page filename
rule (`lint.py` and `pack.py` had byte-identical regexes), the debris
rule (only `pack --spec` applied it, so `mf index` and `mf lint` treated a
Syncthing `.sync-conflict-` copy as a real page), and the directory walk
with its skip list (indexer, lint, and pack each re-implemented the
`os.walk` prune). A rule with two copies drifts (ROADMAP.md's review
checklist, item 1), so they live here and everything imports them.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

# docs/upstream/SPEC.md "Pages": lowercase ASCII letters, digits, hyphens,
# starting and ending with a letter or digit.
SPEC_FILENAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# docs/upstream/SPEC.md: names every reader ignores.
DEBRIS_NAMES = frozenset({".DS_Store", "desktop.ini", "Thumbs.db"})
DEBRIS_INFIX = ".sync-conflict-"

# Directories never walked looking for pages. "raw" is the mf.raw staging
# area (ROADMAP.md 2.2): the spec requires implementations not index it,
# since its entries are freeform session extracts, not pages.
SKIP_DIRS = frozenset({".git", ".venv", "venv", "__pycache__", "node_modules", ".mfgpt", "raw"})
RAW_DIRNAME = "raw"


def is_debris(name: str) -> bool:
    """True for a filename the spec says to ignore outright."""
    return name in DEBRIS_NAMES or name.endswith("~") or DEBRIS_INFIX in name


def walk_field(
    field_dir: Path, *, include_raw: bool = False, include_dotfiles: bool = False
) -> Iterator[Path]:
    """Every file under `field_dir` a memoryfield reader may look at, in
    a stable sorted order. Skip directories and dot-directories are pruned,
    debris is dropped. `raw/` is included only on request (pack wants it,
    index and lint never do). Dotfiles are dropped unless asked for.
    """
    for dirpath, dirnames, filenames in os.walk(field_dir):
        at_root = Path(dirpath) == field_dir
        dirnames[:] = sorted(
            d for d in dirnames
            if (d == RAW_DIRNAME and include_raw and at_root)
            or (d not in SKIP_DIRS and not d.startswith("."))
        )
        for name in sorted(filenames):
            if is_debris(name):
                continue
            if name.startswith(".") and not include_dotfiles:
                continue
            yield Path(dirpath) / name
