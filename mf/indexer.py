"""`mf index` — walk a field's pages, keep mf.sqlite3 in sync.

Incremental on sha256 (PLAN.md's stale-embeddings mitigation): a page
whose sha256 and filename both match what's in the `pages` table is
skipped entirely, no re-parse, no re-embed. Everything this module
writes is derived from the pages on disk, so a page whose file
disappears has its index rows removed too.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import embedder, schema, spec
from .embedder import (  # noqa: F401  (re-exported)
    MODEL_REGISTRY,
    UnknownModelCodeError,
    vec_blob,
)
from .page import NoFrontmatterError, Page, PageParseError, load_page
from .tokens import default_tokenize

# Kept as a name for older importers; the list itself lives in mf/spec.py.
_SKIP_DIRS = spec.SKIP_DIRS


@dataclass
class IndexResult:
    upserted: list[str]
    deleted: list[str]
    unchanged: int
    # uuid -> the files that all claim it. None of them is indexed and any
    # existing row for that uuid is left alone until the author picks one.
    duplicates: dict[str, list[str]] = field(default_factory=dict)
    # field-relative path -> why it was passed over (parse error, not UTF-8,
    # unreadable). Files with no frontmatter at all are not listed: a README
    # in the tree is not a broken page.
    skipped: dict[str, str] = field(default_factory=dict)


@dataclass
class Discovery:
    pages: dict[str, Page]
    duplicates: dict[str, list[str]]
    skipped: dict[str, str]


def discover(field_dir: Path) -> Discovery:
    """Walk `field_dir` for `*.md` files that parse as valid memoryfield
    pages. Files without a frontmatter block are silently not pages --
    that's how a plain README.md or CLAUDE.md in the same tree is told
    apart from an indexable page. Files that have frontmatter but fail to
    parse, or can't be read, are reported in `skipped` rather than
    crashing the walk (one latin-1 note used to abort the whole index).
    Two files carrying one uuid are reported in `duplicates` and neither
    is returned as a page: before this, whichever `os.walk` visited last
    silently won, and which one that was could change between runs.

    `Page.filename` is recorded relative to `field_dir` (POSIX form), not
    absolute: the index has to keep working after the field directory
    moves (a fresh clone, a `pack`/`unpack` round trip). `mf read`
    re-joins it with the field directory it was given.
    """
    pages: dict[str, Page] = {}
    seen: dict[str, list[str]] = {}
    skipped: dict[str, str] = {}
    for path in spec.walk_field(field_dir):
        if path.suffix != ".md":
            continue
        rel = path.relative_to(field_dir).as_posix()
        try:
            page = load_page(path, filename=rel)
        except NoFrontmatterError:
            continue
        except PageParseError as e:
            skipped[rel] = str(e)
            continue
        except OSError as e:
            skipped[rel] = f"unreadable: {e.strerror or e}"
            continue
        seen.setdefault(page.uuid, []).append(rel)
        pages[page.uuid] = page
    duplicates = {uuid: rels for uuid, rels in seen.items() if len(rels) > 1}
    for uuid in duplicates:
        del pages[uuid]
    return Discovery(pages=pages, duplicates=duplicates, skipped=skipped)


def discover_pages(field_dir: Path) -> dict[str, Page]:
    """`discover()`'s pages alone, for callers that only want the map."""
    return discover(field_dir).pages


def _existing(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    rows = conn.execute("SELECT uuid, sha256, filename FROM pages").fetchall()
    return {uuid: (sha, filename) for uuid, sha, filename in rows}


def _embed_pages(
    pages: list[Page], model_code: str
) -> dict[str, list[float]]:
    """Thin wrapper over mf.embedder so tests can monkeypatch the index
    path without loading a model."""
    return embedder.embed_pages(pages, model_code)


_TYPED_LINK_KINDS = ("supersedes", "contradicts", "depends_on")


def _delete_page_rows(
    conn: sqlite3.Connection, uuid: str, *, page_removed: bool
) -> None:
    """Drop everything the index derives from one page's file.

    Typed links (supersedes/contradicts/depends_on) come from the page's
    own frontmatter, so they're rebuilt on every upsert. `co_read` rows
    are NOT derived from the file -- they accumulate from `mf read`
    calls and can't be reconstructed from anything else in the index --
    so an upsert must leave them alone. Before this distinction existed,
    editing a page silently wiped its co_read history on the next
    `mf index`. Only when the page's file is gone (`page_removed`) does
    its co_read history go with it, in both link directions.

    The FTS row shares the page's rowid (schema v3), so it is deleted by
    rowid before the `pages` row goes: `uuid` is UNINDEXED in fts5 and a
    delete by uuid scanned the whole virtual table per page.
    """
    conn.execute(
        "DELETE FROM fts WHERE rowid IN (SELECT rowid FROM pages WHERE uuid = ?)", (uuid,)
    )
    conn.execute("DELETE FROM pages WHERE uuid = ?", (uuid,))
    conn.execute("DELETE FROM sections WHERE uuid = ?", (uuid,))
    conn.execute("DELETE FROM vec WHERE page_uuid = ?", (uuid,))
    placeholders = ",".join("?" for _ in _TYPED_LINK_KINDS)
    conn.execute(
        f"DELETE FROM links WHERE src = ? AND kind IN ({placeholders})",
        (uuid, *_TYPED_LINK_KINDS),
    )
    if page_removed:
        conn.execute(
            "DELETE FROM links WHERE kind = 'co_read' AND (src = ? OR dst = ?)",
            (uuid, uuid),
        )


def _write_page(
    conn: sqlite3.Connection, page: Page, embedding: list[float] | None
) -> None:
    _delete_page_rows(conn, page.uuid, page_removed=False)

    total_tokens = default_tokenize(page.body) + default_tokenize(page.summary)
    cur = conn.execute(
        "INSERT INTO pages (uuid, filename, title, summary, status, "
        "tokens, sha256, updated, writer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (page.uuid, page.filename, page.title, page.summary, page.status,
         total_tokens, page.sha256, page.updated, page.writer),
    )
    rowid = cur.lastrowid

    for section in page.sections:
        conn.execute(
            "INSERT INTO sections (uuid, slug, ordinal, tokens) VALUES (?, ?, ?, ?)",
            (page.uuid, section.slug, section.ordinal, default_tokenize(section.body)),
        )

    conn.execute(
        "INSERT INTO fts (rowid, uuid, title, summary, body) VALUES (?, ?, ?, ?, ?)",
        (rowid, page.uuid, page.title, page.summary, page.body),
    )

    if embedding is not None:
        conn.execute(
            "INSERT INTO vec (page_uuid, embedding) VALUES (?, ?)",
            (page.uuid, vec_blob(embedding)),
        )

    for kind, targets in zip(
        _TYPED_LINK_KINDS, (page.supersedes, page.contradicts, page.depends_on), strict=True
    ):
        for dst in targets:
            conn.execute(
                "INSERT OR REPLACE INTO links (src, dst, kind, weight) "
                "VALUES (?, ?, ?, 1.0)",
                (page.uuid, dst, kind),
            )


def index_page(
    field_dir: Path,
    conn: sqlite3.Connection,
    page_path: Path,
    *,
    page: Page | None = None,
    embedding: list[float] | None = None,
) -> str:
    """Upsert exactly one page (ROADMAP.md 2.8). `mf write` uses this so a
    write only ever indexes the page it validated and gated -- never a
    second, hand-edited page that happens to be sitting in the field
    (that one waits for `mf index`, which is the un-gated path on
    purpose). A caller that already parsed the page and embedded it (the
    dedup gate) passes both in so the file isn't re-read and the model
    isn't run twice. Returns the page's uuid.
    """
    model_code, _ = schema.field_model(conn)
    rel = page_path.relative_to(field_dir).as_posix()
    if page is None or page.filename != rel:
        page = load_page(page_path, filename=rel)
    if embedding is None:
        embedding = _embed_pages([page], model_code).get(page.uuid)
    _write_page(conn, page, embedding)
    conn.commit()
    return page.uuid


def index_field(field_dir: Path, conn: sqlite3.Connection) -> IndexResult:
    model_code, _ = schema.field_model(conn)

    found = discover(field_dir)
    on_disk = found.pages
    existing = _existing(conn)

    to_upsert = [
        page for uuid, page in on_disk.items()
        if existing.get(uuid) != (page.sha256, page.filename)
    ]
    # A uuid claimed by two files keeps whatever row it already has.
    to_delete = [
        uuid for uuid in existing
        if uuid not in on_disk and uuid not in found.duplicates
    ]
    unchanged = len(on_disk) - len(to_upsert)

    embeddings = _embed_pages(to_upsert, model_code)

    for uuid in to_delete:
        _delete_page_rows(conn, uuid, page_removed=True)
    for page in to_upsert:
        _write_page(conn, page, embeddings.get(page.uuid))

    conn.commit()
    return IndexResult(
        upserted=[p.uuid for p in to_upsert],
        deleted=to_delete,
        unchanged=unchanged,
        duplicates=found.duplicates,
        skipped=found.skipped,
    )
