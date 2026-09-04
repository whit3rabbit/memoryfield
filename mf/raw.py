"""`mf raw add` -- append a session extract to `raw/`.

`raw/` is the write path's staging area (PLAN.md sections 2 and 8):
freeform session extracts land here first, `mf index` never sees them
(`mf/spec.py`'s `SKIP_DIRS` skips the directory outright, matching
the spec's "implementations must not index raw/" requirement), and
`consolidate --plan` (ROADMAP.md 4.2) is what turns an entry here into
a real page via `mf write`.

Session-end hooks can double-fire (a retry, a flaky hook, two hooks
racing on the same event) -- `add_raw()` guards against writing the
same extract twice by comparing the new text against the most
recently written entry (found by filename, which sorts chronologically
since filenames are ISO timestamps): if either text is a prefix of the
other, the call is treated as a duplicate and no new file is written.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .spec import RAW_DIRNAME


class EmptyRawTextError(ValueError):
    """Raised when there's no text to append (blank arg and blank stdin)."""


@dataclass
class RawAddResult:
    written: bool
    path: Path

    def as_dict(self) -> dict:
        return {"written": self.written, "path": str(self.path)}


def _raw_dir(field_dir: Path) -> Path:
    return field_dir / RAW_DIRNAME


def _most_recent_entry(raw_dir: Path) -> Path | None:
    entries = sorted(raw_dir.glob("*.md"))
    return entries[-1] if entries else None


def _is_duplicate(new_text: str, existing_text: str) -> bool:
    return new_text.startswith(existing_text) or existing_text.startswith(new_text)


def add_raw(field_dir: Path, text: str) -> RawAddResult:
    text = text.strip()
    if not text:
        raise EmptyRawTextError("no text given")

    raw_dir = _raw_dir(field_dir)
    raw_dir.mkdir(exist_ok=True)

    last = _most_recent_entry(raw_dir)
    if last is not None and _is_duplicate(text, last.read_text(encoding="utf-8").strip()):
        return RawAddResult(written=False, path=last)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = raw_dir / f"{timestamp}.md"
    path.write_text(text + "\n", encoding="utf-8")
    return RawAddResult(written=True, path=path)
