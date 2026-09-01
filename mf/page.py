"""Page — parsing a memoryfield-spec Markdown file with frontmatter.

Full spec per docs/architecture.md's "Pages (canonical)" layer: spec
fields (uuid, title, created, updated) plus extended fields (summary,
status, supersedes, contradicts, depends_on, tags, source, writer).
Body convention: first `##` section is L1 (answer-first), later
sections are L2, addressable as `uuid#slug`.

Uses real YAML (PyYAML) for frontmatter, unlike eval/mf_harness.py's
hand-rolled key:value parser -- that one predates M1 on purpose (see
its docstring); this is the real parser eval never needed to be.
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
# to the identical Python str either way.
_FM_LINE_RE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][\w-]*):[ \t](?P<value>.*)$")


class PageParseError(ValueError):
    """Raised when a Markdown file isn't a valid memoryfield page."""


def slugify(heading: str) -> str:
    slug = _SLUG_RE.sub("-", heading.strip().lower()).strip("-")
    return slug or "section"


@dataclass
class Section:
    slug: str
    heading: str
    ordinal: int
    body: str
    byte_start: int
    byte_end: int


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
    def l1(self) -> str:
        """First section body -- the answer-first portion (150-300 tokens)."""
        return self.sections[0].body if self.sections else self.body


def _split_sections(body: str) -> list[Section]:
    matches = list(_SECTION_RE.finditer(body))
    if not matches:
        return [Section(
            slug="", heading="", ordinal=0, body=body.strip(),
            byte_start=0, byte_end=len(body.encode("utf-8")),
        )]

    out: list[Section] = []
    ordinal = 0
    seen_slugs: dict[str, int] = {}

    if matches[0].start() > 0:
        preamble = body[: matches[0].start()].strip()
        if preamble:
            out.append(Section(
                slug="", heading="", ordinal=ordinal, body=preamble,
                byte_start=0, byte_end=len(preamble.encode("utf-8")),
            ))
            ordinal += 1

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section_body = body[start:end].strip()

        slug = slugify(heading)
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}-{seen_slugs[slug]}"
        else:
            seen_slugs[slug] = 0

        out.append(Section(
            slug=slug, heading=heading, ordinal=ordinal, body=section_body,
            byte_start=len(body[:start].encode("utf-8")),
            byte_end=len(body[:end].encode("utf-8")),
        ))
        ordinal += 1
    return out


def _quote_ambiguous_values(fm_blob: str) -> str:
    """Quote every `key: value` line's value, unless it's empty, already
    quoted, or a flow list (`key: [a, b]`). A quoted plain scalar parses
    to the identical Python str either way, so this is strictly safer
    than trying to detect which specific values would trip up PyYAML's
    plain-scalar scanner.
    """
    out_lines = []
    for line in fm_blob.splitlines():
        m = _FM_LINE_RE.match(line)
        if not m:
            out_lines.append(line)
            continue
        value = m.group("value")
        if not value or value[0] in "[\"'{":
            out_lines.append(line)
            continue
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        out_lines.append(f'{m.group("indent")}{m.group("key")}: "{escaped}"')
    return "\n".join(out_lines)


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def parse_page(text: str, filename: str = "") -> Page:
    """Parse a memoryfield page's raw text. Raises PageParseError if
    `text` isn't a valid memoryfield page (no frontmatter, or missing a
    required field) -- this is how `mf index` tells a page apart from
    an arbitrary Markdown file.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise PageParseError(f"{filename}: no frontmatter block")
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
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def load_page(path: Path, filename: str | None = None) -> Page:
    """Parse the page at `path`. `filename` is what gets recorded as the
    page's identity in the index (mf/indexer.py stores it field-relative
    so an index survives the field directory moving, e.g. a clone or a
    `pack`/`unpack` round trip); it defaults to `path` itself.
    """
    raw = path.read_bytes()
    return parse_page(raw.decode("utf-8"), filename=filename or str(path))
