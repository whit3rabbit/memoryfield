"""Page — parsing a memoryfield-spec Markdown file with frontmatter.

Full spec per docs/architecture.md's "Pages (canonical)" layer: spec
fields (uuid, title, created, updated) plus extended fields (summary,
status, supersedes, contradicts, depends_on, tags, source, writer).
Body convention: the first `##` section is L1 (answer-first), later
sections are L2, addressable as `uuid#slug`. Prose before the first
`##` (a preamble) belongs to L1 rather than displacing it: before that
rule, a page opening with one sentence and then `## Answer` was embedded
and read at L1 as the sentence alone.

Uses real YAML (PyYAML) for frontmatter. eval/mf_harness.py's own
hand-rolled parser predates this one and now delegates to it.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Plain (unquoted) YAML scalars reject a long, easy-to-hit list of
# leading/embedded characters -- an unescaped ": " (this project's own
# "Topic: specific question" title convention), a leading backtick (a
# summary that opens with an inline-code term, e.g. `` `Idempotency-Key`
# ties... ``), and others. Rather than track every case PyYAML's scanner
# rejects, or require the whole corpus to requote itself to a stricter
# convention, quote every scalar value for the author before handing
# the block to yaml.safe_load() -- a quoted plain string round-trips
# to the identical Python str either way. Block scalars (`key: |`,
# `key: >`) are the one value shape that must not be quoted: the
# indicator and every line indented under it pass through untouched.
_FM_LINE_RE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][\w-]*):[ \t](?P<value>.*)$")
_BLOCK_INDICATOR_RE = re.compile(r"^[|>][+-]?\d*$")


class PageParseError(ValueError):
    """Raised when a Markdown file isn't a valid memoryfield page."""


class NoFrontmatterError(PageParseError):
    """The file has no frontmatter block at all: a README, not a broken
    page. Walkers skip these silently and report every other
    PageParseError."""


def slugify(heading: str) -> str:
    slug = _SLUG_RE.sub("-", heading.strip().lower()).strip("-")
    return slug or "section"


def page_path(field_dir: Path, filename: str) -> Path:
    """Where `pages.filename` lives on disk. Stored field-relative since
    mf/indexer.py's discover_pages(); an index built before that holds
    absolute paths, used as-is until the next `mf index` rewrites them.
    """
    path = Path(filename)
    return path if path.is_absolute() else field_dir / path


@dataclass
class Section:
    slug: str
    heading: str
    ordinal: int
    body: str


@dataclass
class Page:
    uuid: str
    title: str
    filename: str
    summary: str = ""
    status: str = "active"
    created: str = ""
    updated: str = ""
    writer: str = ""
    source: str = ""
    tags: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    contradicts: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    body: str = ""
    sections: list[Section] = field(default_factory=list)
    sha256: str = ""

    @property
    def l1_end_index(self) -> int:
        """Index of the last section that belongs to L1: the first headed
        section, or the lone preamble when there are no headings."""
        for i, s in enumerate(self.sections):
            if s.heading:
                return i
        return 0

    @property
    def l1(self) -> str:
        """The answer-first portion: any preamble plus the first `##`
        section (150-300 tokens by convention)."""
        if not self.sections:
            return self.body
        parts = [s.body for s in self.sections[: self.l1_end_index + 1] if s.body]
        return "\n\n".join(parts)

    @property
    def l2(self) -> str:
        """Everything after L1."""
        return "\n\n".join(s.body for s in self.sections[self.l1_end_index + 1:])

    @property
    def slug(self) -> str:
        """The page's slug for `claims`/multi-writer purposes (ROADMAP.md
        4.3): the filename stem. Two writers collide on this, not on the
        uuid (which each mints independently) -- e.g. `backend/foo.md`
        and `frontend/foo.md` share slug `foo` even though they're
        different pages.
        """
        return Path(self.filename).stem


def _split_sections(body: str) -> list[Section]:
    matches = list(_SECTION_RE.finditer(body))
    if not matches:
        return [Section(slug="", heading="", ordinal=0, body=body.strip())]

    out: list[Section] = []
    ordinal = 0
    seen_slugs: set[str] = set()

    if matches[0].start() > 0:
        preamble = body[: matches[0].start()].strip()
        if preamble:
            out.append(Section(slug="", heading="", ordinal=ordinal, body=preamble))
            ordinal += 1

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section_body = body[start:end].strip()

        base = slugify(heading)
        slug = base
        n = 1
        # `Notes`, `Notes 1`, `Notes` must not yield `notes-1` twice: the
        # sections table's primary key is (uuid, slug).
        while slug in seen_slugs:
            slug = f"{base}-{n}"
            n += 1
        seen_slugs.add(slug)

        out.append(Section(slug=slug, heading=heading, ordinal=ordinal, body=section_body))
        ordinal += 1
    return out


def _quote_ambiguous_values(fm_blob: str) -> str:
    """Quote every `key: value` line's value, unless it's empty, already
    quoted, a flow collection (`key: [a, b]`), or a block scalar
    indicator (`key: |`), whose indented body is passed through as-is.
    A quoted plain scalar parses to the identical Python str either way,
    so this is strictly safer than trying to detect which specific values
    would trip up PyYAML's plain-scalar scanner. Trailing `\\r` (CRLF
    files) is dropped so it never ends up inside a quoted value.
    """
    lines = [line.rstrip("\r") for line in fm_blob.splitlines()]
    out_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _FM_LINE_RE.match(line)
        if not m:
            out_lines.append(line)
            i += 1
            continue
        value = m.group("value").strip()
        if _BLOCK_INDICATOR_RE.match(value):
            out_lines.append(line)
            key_indent = len(m.group("indent"))
            i += 1
            while i < len(lines):
                nxt = lines[i]
                deeper = len(nxt) - len(nxt.lstrip(" ")) > key_indent
                if nxt.strip() == "" or deeper:
                    out_lines.append(nxt)
                    i += 1
                else:
                    break
            continue
        if not value or value[0] in "[\"'{":
            out_lines.append(line)
        else:
            raw = m.group("value")
            escaped = raw.replace("\\", "\\\\").replace('"', '\\"')
            out_lines.append(f'{m.group("indent")}{m.group("key")}: "{escaped}"')
        i += 1
    return "\n".join(out_lines)


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def parse_page(text: str, filename: str = "", sha256: str | None = None) -> Page:
    """Parse a memoryfield page's raw text. Raises PageParseError if
    `text` isn't a valid memoryfield page (NoFrontmatterError when there
    is no block at all, PageParseError for a block missing a required
    field) -- this is how `mf index` tells a page apart from an
    arbitrary Markdown file. `sha256` is the digest of the file's raw
    bytes when the caller has them (load_page); otherwise it is computed
    from `text`.
    """
    text = text.lstrip("﻿")
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise NoFrontmatterError(f"{filename}: no frontmatter block")
    fm_blob, body = m.group(1), m.group(2)

    try:
        fm = yaml.safe_load(_quote_ambiguous_values(fm_blob))
    except yaml.YAMLError as e:
        raise PageParseError(f"{filename}: invalid frontmatter YAML: {e}") from e
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        raise PageParseError(f"{filename}: frontmatter is not a mapping")

    uuid = fm.get("uuid")
    if not uuid:
        raise PageParseError(f"{filename}: missing required 'uuid' field")
    title = fm.get("title")
    if not title:
        raise PageParseError(f"{filename}: missing required 'title' field")

    body = body.strip()
    return Page(
        uuid=str(uuid),
        title=str(title),
        filename=filename,
        summary=str(fm.get("summary", "")),
        status=str(fm.get("status", "active")),
        created=str(fm.get("created", "")),
        updated=str(fm.get("updated", "")),
        writer=str(fm.get("writer", "")),
        source=str(fm.get("source", "")),
        tags=_as_list(fm.get("tags")),
        supersedes=_as_list(fm.get("supersedes")),
        contradicts=_as_list(fm.get("contradicts")),
        depends_on=_as_list(fm.get("depends_on")),
        body=body,
        sections=_split_sections(body),
        sha256=sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def load_page(path: Path, filename: str | None = None) -> Page:
    """Parse the page at `path`. `filename` is what gets recorded as the
    page's identity in the index (mf/indexer.py stores it field-relative
    so an index survives the field directory moving, e.g. a clone or a
    `pack`/`unpack` round trip); it defaults to `path` itself. The
    recorded sha256 is over the raw bytes, BOM included, so it matches
    what `mf search`'s stale check and `mf pack` hash off disk.
    """
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise PageParseError(f"{filename or path}: not UTF-8 ({e.reason} at byte {e.start})") from e
    return parse_page(
        text, filename=filename or str(path), sha256=hashlib.sha256(raw).hexdigest()
    )
