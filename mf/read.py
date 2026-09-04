"""`mf read` — return exactly one slice of a page, logging the read.

Per docs/architecture.md's "Read" layer (PLAN.md: `read uuid[#section]
--tier L1|L2`): a `uuid#slug` ref returns that section verbatim; a bare
uuid returns the L1 (preamble plus first section, answer-first) or L2
(everything after L1) tier, as mf.page.Page defines them. Every
successful read is logged to the `reads` table, and when a single call
reads more than one page, `co_read` weight in `links` is bumped for
every pair -- the only path that ever populates `co_read` (search's
kNN/typed-link neighbors are the other two sources, computed at query
time instead of stored; see mf/search.py's `_neighbors()`). An agent
that reads a page by `cat`ing the file instead of going through this
module leaves no trace here -- an accepted gap, PLAN.md section 10.

Page content itself is never cached in the index: `mf.sqlite3` only
stores enough (`filename`, relative to the field directory) to find the
page again, and this module re-parses it fresh off disk every call via
mf.page.load_page(), the same parser `mf index` uses. A page the index
knows but the disk no longer has (or no longer parses) is reported as
not found with a pointer at `mf index`, not as a traceback.
"""
from __future__ import annotations

import uuid as uuid_mod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection

from .page import PageParseError, load_page, page_path
from .tokens import default_tokenize

DEFAULT_TIER = "L1"
TIERS = ("L1", "L2")


class PageNotFoundError(LookupError):
    """Raised when a ref's uuid isn't in the pages table, or its file is
    gone or unparsable since `mf index`."""


class SectionNotFoundError(LookupError):
    """Raised when a ref's #section slug doesn't exist on that page."""


@dataclass
class ReadResult:
    uuid: str
    title: str
    body: str
    tokens: int
    section: str | None = None
    tier: str | None = None

    def as_dict(self) -> dict:
        d: dict = {
            "uuid": self.uuid, "title": self.title,
            "body": self.body, "tokens": self.tokens,
        }
        if self.section is not None:
            d["section"] = self.section
        if self.tier is not None:
            d["tier"] = self.tier
        return d


def parse_ref(ref: str) -> tuple[str, str | None]:
    """`uuid` -> (uuid, None); `uuid#slug` -> (uuid, "slug")."""
    uuid, sep, section = ref.partition("#")
    return uuid, (section if sep else None)


def _page_filename(conn: Connection, uuid: str) -> tuple[str, str]:
    row = conn.execute(
        "SELECT title, filename FROM pages WHERE uuid = ?", (uuid,)
    ).fetchone()
    if row is None:
        raise PageNotFoundError(uuid)
    return row[0], row[1]


# Older name; mf.page.page_path is the one implementation.
_resolve_path = page_path


def _read_one(
    conn: Connection, ref: str, tier: str | None, field_dir: Path
) -> ReadResult:
    uuid, section = parse_ref(ref)
    title, filename = _page_filename(conn, uuid)
    try:
        page = load_page(page_path(field_dir, filename))
    except (OSError, PageParseError) as e:
        raise PageNotFoundError(
            f"{uuid}: {filename} is missing or unparsable since `mf index` ({e})"
        ) from e

    if section is not None:
        for s in page.sections:
            if s.slug == section:
                return ReadResult(
                    uuid=uuid, title=title, body=s.body,
                    tokens=default_tokenize(s.body), section=section,
                )
        raise SectionNotFoundError(f"{uuid}#{section}")

    resolved_tier = tier or DEFAULT_TIER
    body = page.l1 if resolved_tier == "L1" else page.l2
    return ReadResult(
        uuid=uuid, title=title, body=body,
        tokens=default_tokenize(body), tier=resolved_tier,
    )


def _log_read(conn: Connection, result: ReadResult, call_id: str) -> None:
    # call_id groups the rows of one read() call, so co_read (which is
    # otherwise not derivable from anything, CLAUDE.md gotcha 33) can be
    # rebuilt from `reads` alone: every pair of distinct uuids sharing a
    # call_id is one co_read increment.
    conn.execute(
        "INSERT INTO reads (uuid, section, tier, read_at, call_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (result.uuid, result.section, result.tier,
         datetime.now(UTC).isoformat(), call_id),
    )


def _bump_co_read(conn: Connection, uuids: list[str]) -> None:
    # Canonical (src < dst) ordering so weight accumulates on one row per
    # pair across calls instead of splitting across both directions.
    unique = sorted(set(uuids))
    for i in range(len(unique)):
        for j in range(i + 1, len(unique)):
            conn.execute(
                "INSERT INTO links (src, dst, kind, weight) "
                "VALUES (?, ?, 'co_read', 1.0) "
                "ON CONFLICT(src, dst, kind) DO UPDATE SET weight = weight + 1",
                (unique[i], unique[j]),
            )


def read(
    conn: Connection,
    refs: list[str],
    tier: str | None = None,
    *,
    field_dir: Path,
) -> list[ReadResult]:
    """`field_dir` is the directory `mf.sqlite3` lives in; `pages.filename`
    is stored relative to it (mf/indexer.py's discover_pages()).
    """
    if tier is not None and tier not in TIERS:
        raise ValueError(f"tier must be one of {', '.join(TIERS)}, not {tier!r}")
    results = [_read_one(conn, ref, tier, field_dir) for ref in refs]
    call_id = uuid_mod.uuid4().hex
    for result in results:
        _log_read(conn, result, call_id)
    if len(refs) > 1:
        _bump_co_read(conn, [r.uuid for r in results])
    conn.commit()
    return results
