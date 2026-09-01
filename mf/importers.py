"""`mf import claude-memory <dir>` and `mf import wiki <dir>` (ROADMAP.md 3.2).

Both turn an existing collection of Markdown notes into memoryfield
pages inside the field and index them. Imports are the un-gated bulk
path on purpose (docs/architecture.md, Write layer): the dedup gate is
for one page at a time, and an import's job is to move what exists.
Run `mf lint` afterwards for the conventions.

Formats, from real examples rather than the plan's one-liners:

  claude-memory: Claude Code's auto-memory directory. `MEMORY.md` is an
  index of `- [Title](file.md) — hook` lines; each topic file carries
  frontmatter `name`, `description`, and `metadata.type`
  (user | feedback | project | reference) above a Markdown body. Title
  comes from the index link text (fallback: `name`), summary from
  `description` (fallback: the index hook), tag from `metadata.type`,
  uuid from `name` (fallback: file stem). An index line whose file is
  missing still becomes a stub-only page (title + summary, no body).

  wiki: a Karpathy-style wiki. `index.md` lists pages as
  `- [Title](relative/path.md): one-line description` (or with ` — `
  or ` - ` before the description). Subdirectories flatten into the
  filename (`a/b.md` -> `a-b.md`), the uuid is the flattened stem, the
  title is the link text or the file's first `# ` heading, the summary
  is the index description or the first paragraph, and the body is the
  file minus its H1. Markdown files not in the index import too, with
  heading and first paragraph standing in.

Uuids are derived from source paths, so re-importing updates the same
pages in place. `source` on every page points at the original file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection

from . import indexer
from .page import FRONTMATTER_RE, PageParseError, _quote_ambiguous_values, slugify

_INDEX_LINE_RE = re.compile(
    r"^\s*[-*]\s+\[(?P<title>[^\]]+)\]\((?P<path>[^)]+)\)\s*(?:[—:\-]\s*(?P<desc>.*))?$"
)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class ImportedPage:
    uuid: str
    dest: str          # field-relative
    source: str
    title: str

    def as_dict(self) -> dict:
        return {"uuid": self.uuid, "dest": self.dest, "source": self.source, "title": self.title}


@dataclass
class ImportResult:
    kind: str
    pages: list[ImportedPage] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    dry_run: bool = False
    indexed: int = 0

    def as_dict(self) -> dict:
        return {
            "kind": self.kind, "dry_run": self.dry_run, "indexed": self.indexed,
            "pages": [p.as_dict() for p in self.pages], "skipped": self.skipped,
        }


def _yaml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def render_page(
    uuid: str, title: str, summary: str, body: str, *,
    source: str = "", tags: list[str] | None = None,
    created: str = "", updated: str = "",
) -> str:
    lines = [
        "---",
        f"uuid: {_yaml_str(uuid)}",
        f"title: {_yaml_str(title)}",
        f"summary: {_yaml_str(summary)}",
        "status: active",
    ]
    if tags:
        lines.append("tags: [" + ", ".join(_yaml_str(t) for t in tags) + "]")
    if source:
        lines.append(f"source: {_yaml_str(source)}")
    if created:
        lines.append(f"created: {created}")
    if updated:
        lines.append(f"updated: {updated}")
    lines.append("---")
    text = "\n".join(lines) + "\n\n" + body.strip() + ("\n" if body.strip() else "")
    return text


def _split_frontmatter(text: str) -> tuple[dict, str]:
    import yaml

    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(_quote_ambiguous_values(m.group(1))) or {}
    except yaml.YAMLError:
        return {}, text
    return (fm if isinstance(fm, dict) else {}), m.group(2)


def _first_paragraph(body: str) -> str:
    for block in re.split(r"\n\s*\n", body.strip()):
        block = block.strip()
        if block and not block.startswith("#"):
            return " ".join(block.split())[:300]
    return ""


def _dates(path: Path) -> tuple[str, str]:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, UTC).date().isoformat()
    except OSError:
        return "", ""
    return mtime, mtime


def _parse_index(index_path: Path) -> list[tuple[str, str, str]]:
    """(title, relative path, description) per index line, in order."""
    if not index_path.exists():
        return []
    out = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        m = _INDEX_LINE_RE.match(line)
        if m:
            out.append((m.group("title").strip(), m.group("path").strip(), (m.group("desc") or "").strip()))
    return out


def _write_pages(
    field_dir: Path, conn: Connection, subdir: str, rendered: list[tuple[str, str, str, str]],
    result: ImportResult, dry_run: bool,
) -> ImportResult:
    """rendered: (uuid, filename, source, page text)."""
    out_dir = field_dir / subdir
    for uuid, filename, source, text in rendered:
        rel = f"{subdir}/{filename}"
        title = re.search(r'^title: "(.*)"$', text, re.MULTILINE)
        result.pages.append(ImportedPage(uuid, rel, source, title.group(1) if title else uuid))
        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / filename).write_text(text, encoding="utf-8")
    result.dry_run = dry_run
    if not dry_run and rendered:
        result.indexed = len(indexer.index_field(field_dir, conn).upserted)
    return result


def import_claude_memory(src: Path, field_dir: Path, conn: Connection, dry_run: bool = False) -> ImportResult:
    src = src.resolve()
    field_dir = field_dir.resolve()
    result = ImportResult(kind="claude-memory")
    index = _parse_index(src / "MEMORY.md")
    by_file = {path: (title, desc) for title, path, desc in index}
    rendered: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()

    for path in sorted(src.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        name = str(fm.get("name") or path.stem)
        uuid = slugify(name)
        idx_title, idx_desc = by_file.get(path.name, ("", ""))
        title = idx_title or name.replace("-", " ")
        summary = str(fm.get("description") or idx_desc or _first_paragraph(body))
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        tags = [str(meta["type"])] if meta and meta.get("type") else []
        created, updated = _dates(path)
        rendered.append((uuid, f"{uuid}.md", str(path),
                         render_page(uuid, title, summary, body, source=str(path), tags=tags,
                                     created=created, updated=updated)))
        seen.add(path.name)

    for title, rel, desc in index:
        if rel in seen:
            continue
        if not desc and not title:
            continue
        uuid = slugify(Path(rel).stem)
        result.skipped.append(f"{rel}: listed in MEMORY.md but missing; imported as a stub-only page")
        rendered.append((uuid, f"{uuid}.md", str(src / "MEMORY.md"),
                         render_page(uuid, title, desc or title, "", source=str(src / "MEMORY.md"))))

    return _write_pages(field_dir, conn, "claude-memory", rendered, result, dry_run)


def import_wiki(src: Path, field_dir: Path, conn: Connection, dry_run: bool = False) -> ImportResult:
    src = src.resolve()
    field_dir = field_dir.resolve()
    result = ImportResult(kind="wiki")
    index = _parse_index(src / "index.md")
    by_path: dict[str, tuple[str, str]] = {}
    for title, rel, desc in index:
        try:
            key = (src / rel).resolve().relative_to(src).as_posix()
        except ValueError:
            result.skipped.append(f"{rel}: index link points outside the wiki")
            continue
        by_path[key] = (title, desc)

    rendered: list[tuple[str, str, str, str]] = []
    for path in sorted(src.rglob("*.md")):
        rel = path.relative_to(src).as_posix()
        if path.name == "index.md" or any(part.startswith(".") for part in path.parts):
            continue
        fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        h1 = _H1_RE.search(body)
        idx_title, idx_desc = by_path.get(rel, ("", ""))
        title = idx_title or (h1.group(1).strip() if h1 else str(fm.get("title") or path.stem.replace("-", " ")))
        if h1:
            body = body[: h1.start()] + body[h1.end():]
        summary = idx_desc or str(fm.get("summary") or fm.get("description") or _first_paragraph(body))
        flat = slugify(rel[:-3])  # a/b.md -> a-b
        if not flat:
            result.skipped.append(f"{rel}: could not derive a filename")
            continue
        created, updated = _dates(path)
        rendered.append((flat, f"{flat}.md", str(path),
                         render_page(flat, title, summary, body, source=str(path),
                                     created=created, updated=updated)))
    return _write_pages(field_dir, conn, "wiki", rendered, result, dry_run)


def verify_imported(field_dir: Path, result: ImportResult) -> list[str]:
    """Which imported files fail to parse as pages (should be none)."""
    from .page import load_page

    bad = []
    for p in result.pages:
        try:
            load_page(field_dir / p.dest)
        except PageParseError as e:
            bad.append(str(e))
    return bad
