"""`mf lint` -- enforce the writing conventions (PLAN.md section 5,
docs/architecture.md "Writing conventions") and report index drift.

Load-bearing, not cosmetic (CLAUDE.md gotcha 16): every retrieval
number this project has measured holds because summaries are written as
answers and pages stay small. The linter checks shape, not quality
(PLAN.md section 10): it can tell a five-word summary from a sentence,
not a good sentence from a bad one.

Severities: `error` (the page will misbehave in search or index),
`warning` (a convention the eval depends on), `info` (advice). `--check`
fails on errors and warnings. Info findings print only with `--all`,
because two of them (missing `source`, no typed links) apply to most
pages in a young field.

Every check is grounded in what the 157-page eval corpus actually does
(ROADMAP.md 2.3): all of it opens with `## Answer`, 32 pages carry a
`## Don't` section, none carry tables, and none carry typed links.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection

from .indexer import _SKIP_DIRS, _TYPED_LINK_KINDS
from .page import Page, PageParseError, load_page
from .tokens import default_tokenize

# PLAN.md section 5 says 300-800 tokens per page. The eval corpus that
# produced every retrieval number averages ~240 and not one of its 157
# pages reaches 300 (ROADMAP.md 2.3), so 300 is not a floor the
# evidence supports. The headers rule keeps 300 as its cutoff; the
# short-page note fires only for a page that is little more than a stub.
TOKENS_MIN = 100
TOKENS_HEADERS = 300
TOKENS_MAX = 800
BYTES_MAX = 8 * 1024
SUMMARY_MIN_WORDS = 5

_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
_RELATIVE_TIME_RE = re.compile(
    r"\b(last (week|month|year|night)|yesterday|recently|currently|"
    r"\d+ (days?|weeks?|months?) ago|as of (today|now))\b",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(r"\b(never|don't|do not|must not|avoid)\b", re.IGNORECASE)
_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_TOPIC_PREFIX_RE = re.compile(
    r"^(notes? (on|about)|about|overview of|information (on|about)|"
    r"details (on|about)|how to|misc)\b",
    re.IGNORECASE,
)
_DONT_SLUG = "don-t"

Severity = str  # "error" | "warning" | "info"


@dataclass
class Finding:
    severity: Severity
    code: str
    filename: str
    message: str
    uuid: str = ""

    def as_dict(self) -> dict:
        return {
            "severity": self.severity, "code": self.code,
            "filename": self.filename, "uuid": self.uuid, "message": self.message,
        }


@dataclass
class LintResult:
    findings: list[Finding] = field(default_factory=list)
    pages: int = 0

    def count(self, severity: Severity) -> int:
        return sum(f.severity == severity for f in self.findings)

    @property
    def failed(self) -> bool:
        return any(f.severity in ("error", "warning") for f in self.findings)

    def as_dict(self) -> dict:
        return {
            "pages": self.pages,
            "errors": self.count("error"),
            "warnings": self.count("warning"),
            "info": self.count("info"),
            "findings": [f.as_dict() for f in self.findings],
        }


def _walk(field_dir: Path) -> list[tuple[str, Page | None, str | None]]:
    """Every `.md` under the field: (relative filename, page, parse error).
    Unlike indexer.discover_pages() this keeps duplicates (two files, one
    uuid) and parse errors, both of which lint has to report.
    """
    out: list[tuple[str, Page | None, str | None]] = []
    for dirpath, dirnames, filenames in os.walk(field_dir):
        dirnames[:] = sorted(
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        )
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = Path(dirpath) / name
            rel = path.relative_to(field_dir).as_posix()
            try:
                out.append((rel, load_page(path, filename=rel), None))
            except PageParseError as e:
                out.append((rel, None, str(e)))
    return out


def _page_checks(rel: str, page: Page, raw_bytes: int, add) -> None:
    tokens = default_tokenize(page.body) + default_tokenize(page.summary)

    if raw_bytes > BYTES_MAX:
        add("error", "oversize", f"{raw_bytes} bytes, ceiling is {BYTES_MAX}")
    elif tokens > TOKENS_MAX:
        add("warning", "long-page", f"~{tokens} tokens, ceiling is {TOKENS_MAX}")
    elif tokens < TOKENS_MIN:
        add("info", "short-page", f"~{tokens} tokens; little more than a stub")

    summary = page.summary.strip()
    if not summary:
        add("error", "missing-summary", "no summary; the stub is the answer, and this page has none")
    else:
        words = summary.split()
        if len(words) < SUMMARY_MIN_WORDS:
            add("warning", "summary-shape", f"summary is {len(words)} words; write it as the answer, not the topic")
        elif summary.lower().rstrip(".") == page.title.lower().rstrip("."):
            add("warning", "summary-shape", "summary repeats the title; write it as the answer")
        elif _TOPIC_PREFIX_RE.match(summary):
            add("warning", "summary-shape", f"summary reads as a topic ({words[0]!r} ...); write it as the answer")

    if _TABLE_RE.search(page.body):
        add("warning", "table", "markdown table in body; use `key: value` lines")

    for m in _SHA_RE.finditer(page.body):
        add("warning", "copied-state", f"40-hex SHA {m.group(0)[:12]}... in body; point at the ref, don't copy the value")
        break
    m = _RELATIVE_TIME_RE.search(page.body) or _RELATIVE_TIME_RE.search(page.summary)
    if m:
        add("warning", "copied-state", f"relative time {m.group(0)!r}; use an ISO date or drop it")

    slugs = [s.slug for s in page.sections]
    has_dont = _DONT_SLUG in slugs
    if not has_dont:
        prose = "\n".join(s.body for s in page.sections)
        m = _NEGATION_RE.search(prose)
        if m:
            add("info", "negation-in-prose",
                f"{m.group(0)!r} appears in prose with no `## Don't` section; a warning buried in prose is one search won't surface")

    headed = [s for s in page.sections if s.heading and s.slug != _DONT_SLUG]
    if tokens < TOKENS_HEADERS and len(headed) > 1:
        add("warning", "headers-under-300",
            f"{len(headed)} headed sections in a ~{tokens}-token page; one section until {TOKENS_HEADERS} tokens (`## Don't` excepted)")

    if not page.source:
        add("info", "missing-source", "no `source`; fill it if this came from somewhere citable")

    if page.status not in ("active", "superseded", "contested"):
        add("error", "bad-status", f"status {page.status!r}; expected active, superseded, or contested")


def lint_field(field_dir: Path, conn: Connection | None = None) -> LintResult:
    field_dir = field_dir.resolve()
    result = LintResult()
    entries = _walk(field_dir)

    def adder(rel: str, uuid: str):
        def add(severity: Severity, code: str, message: str) -> None:
            result.findings.append(Finding(severity, code, rel, message, uuid))
        return add

    pages: dict[str, tuple[str, Page]] = {}
    for rel, page, err in entries:
        if page is None:
            if err and "no frontmatter block" not in err:
                result.findings.append(Finding("warning", "invalid-page", rel, err.split(": ", 1)[-1]))
            continue
        result.pages += 1
        add = adder(rel, page.uuid)
        if page.uuid in pages:
            add("error", "duplicate-uuid", f"uuid also used by {pages[page.uuid][0]}")
        else:
            pages[page.uuid] = (rel, page)
        _page_checks(rel, page, (field_dir / rel).stat().st_size, add)

    # Slug collisions (ROADMAP.md 4.3): two active pages with the same
    # filename stem are what `mf claim` exists to prevent going forward,
    # but nothing stops a page written by hand or without claiming
    # first. Superseded/contested pages are exempt -- that's the
    # resolved state this check is nudging toward.
    by_slug: dict[str, list[tuple[str, Page]]] = {}
    for rel, page in pages.values():
        by_slug.setdefault(page.slug, []).append((rel, page))
    for slug, entries in by_slug.items():
        active = [(rel, page) for rel, page in entries if page.status == "active"]
        if len(active) < 2:
            continue
        for rel, page in active:
            others = ", ".join(r for r, p in active if p.uuid != page.uuid)
            add = adder(rel, page.uuid)
            add("warning", "contested-slug",
                f"slug {slug!r} shared with {others}; likely two writers on one topic -- "
                "mark one `status: contested` (or supersede it) once you've compared them")

    # Link-level checks need every page.
    superseded_by: dict[str, str] = {}
    linked: set[str] = set()
    for rel, page in pages.values():
        add = adder(rel, page.uuid)
        for kind, targets in zip(_TYPED_LINK_KINDS, (page.supersedes, page.contradicts, page.depends_on)):
            for dst in targets:
                if dst not in pages:
                    add("error", "dangling-link", f"{kind} -> {dst!r}, which is not a page in this field")
                    continue
                linked.add(dst)
                linked.add(page.uuid)
                if kind == "supersedes":
                    superseded_by[dst] = page.uuid
    for rel, page in pages.values():
        add = adder(rel, page.uuid)
        if page.uuid in superseded_by and page.status == "active":
            add("warning", "active-but-superseded",
                f"status is active but {superseded_by[page.uuid]} supersedes it; set status: superseded")
        if page.status == "superseded" and page.uuid not in superseded_by:
            add("warning", "superseded-not-linked",
                "status is superseded but no page's `supersedes` names it; search will still show it as a full stub")
        if page.uuid not in linked:
            add("info", "orphan", "no typed links in or out")

    # Index drift (only with a connection).
    if conn is not None:
        indexed = {
            uuid: (filename, sha) for uuid, filename, sha in
            conn.execute("SELECT uuid, filename, sha256 FROM pages").fetchall()
        }
        for rel, page in pages.values():
            add = adder(rel, page.uuid)
            if page.uuid not in indexed:
                add("warning", "unindexed", "on disk but not in the index; run `mf index`")
            elif indexed[page.uuid][1] != page.sha256:
                add("warning", "stale-index", "changed since `mf index`; search will refuse it until reindexed")
        for uuid, (filename, _sha) in indexed.items():
            if uuid not in pages:
                result.findings.append(Finding("warning", "missing-file", filename,
                                               "in the index but not on disk; run `mf index`", uuid))

    order = {"error": 0, "warning": 1, "info": 2}
    result.findings.sort(key=lambda f: (order[f.severity], f.filename, f.code))
    return result


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
