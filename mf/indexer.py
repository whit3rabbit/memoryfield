"""`mf index` — walk a field's pages, keep mf.sqlite3 in sync.

Incremental on sha256 (PLAN.md's stale-embeddings mitigation): a page
whose sha256 already matches what's in the `pages` table is skipped
entirely, no re-parse, no re-embed. Everything this module writes is
derived from the pages on disk, so a page whose file disappears has
its index rows removed too.
"""
from __future__ import annotations

import fnmatch
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import embedder, schema
from .embedder import (  # noqa: F401  (re-exported)
    MODEL_REGISTRY,
    UnknownModelCodeError,
    vec_literal,
)
from .page import Page, PageParseError, load_page
from .tokens import default_tokenize

# Directories never walked looking for pages. "raw" is the mf.raw
# staging area (ROADMAP.md 2.2) -- PLAN.md's spec requires
# implementations not index it, since its entries are freeform session
# extracts, not memoryfield pages.
_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".mfgpt", "raw"}

@dataclass
class IndexResult:
    upserted: list[str]
    deleted: list[str]
    unchanged: int


def discover_pages(field_dir: Path) -> dict[str, Page]:
    """Walk `field_dir` for `*.md` files that parse as valid memoryfield
    pages. Files without a frontmatter block (or missing required
    fields) are silently not pages -- that's how a plain README.md or
    CLAUDE.md in the same tree is told apart from an indexable page.

    `Page.filename` is recorded relative to `field_dir` (POSIX form), not
    absolute: the index has to keep working after the field directory
    moves (a fresh clone, a `pack`/`unpack` round trip). `mf read`
    re-joins it with the field directory it was given.
    """
    pages: dict[str, Page] = {}
    for dirpath, dirnames, filenames in os.walk(field_dir):
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for name in fnmatch.filter(filenames, "*.md"):
            path = Path(dirpath) / name
            try:
                page = load_page(path, filename=path.relative_to(field_dir).as_posix())
            except PageParseError:
                continue
            pages[page.uuid] = page
    return pages


def _existing_sha256(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT uuid, sha256 FROM pages").fetchall()
    return {uuid: sha for uuid, sha in rows}


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
    """
    conn.execute("DELETE FROM pages WHERE uuid = ?", (uuid,))
    conn.execute("DELETE FROM sections WHERE uuid = ?", (uuid,))
    conn.execute("DELETE FROM fts WHERE uuid = ?", (uuid,))
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
    conn.execute(
        "INSERT INTO pages (uuid, filename, title, summary, status, "
        "tokens, sha256, updated, writer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (page.uuid, page.filename, page.title, page.summary, page.status,
         total_tokens, page.sha256, page.updated, page.writer),
    )

    for section in page.sections:
        conn.execute(
            "INSERT INTO sections (uuid, slug, ordinal, byte_start, "
            "byte_end, tokens) VALUES (?, ?, ?, ?, ?, ?)",
            (page.uuid, section.slug, section.ordinal, section.byte_start,
             section.byte_end, default_tokenize(section.body)),
        )

    conn.execute(
        "INSERT INTO fts (uuid, title, summary, body) VALUES (?, ?, ?, ?)",
        (page.uuid, page.title, page.summary, page.body),
    )

    if embedding is not None:
        conn.execute(
            "INSERT INTO vec (page_uuid, embedding) VALUES (?, ?)",
            (page.uuid, vec_literal(embedding)),
        )

    for kind, targets in zip(
        _TYPED_LINK_KINDS, (page.supersedes, page.contradicts, page.depends_on)
    ):
        for dst in targets:
            conn.execute(
                "INSERT OR REPLACE INTO links (src, dst, kind, weight) "
                "VALUES (?, ?, ?, 1.0)",
                (page.uuid, dst, kind),
            )


def index_page(field_dir: Path, conn: sqlite3.Connection, page_path: Path) -> str:
    """Upsert exactly one page (ROADMAP.md 2.8). `mf write` uses this so a
    write only ever indexes the page it validated and gated -- never a
    second, hand-edited page that happens to be sitting in the field
    (that one waits for `mf index`, which is the un-gated path on
    purpose). Returns the page's uuid.
    """
    model_code = schema.get_config(conn, "model_code") or schema.DEFAULT_MODEL_CODE
    page = load_page(page_path, filename=page_path.relative_to(field_dir).as_posix())
    embeddings = _embed_pages([page], model_code)
    _write_page(conn, page, embeddings.get(page.uuid))
    conn.commit()
    return page.uuid


def index_field(field_dir: Path, conn: sqlite3.Connection) -> IndexResult:
    model_code = schema.get_config(conn, "model_code") or schema.DEFAULT_MODEL_CODE

    on_disk = discover_pages(field_dir)
    existing = _existing_sha256(conn)

    to_upsert = [
        page for uuid, page in on_disk.items()
        if existing.get(uuid) != page.sha256
    ]
    to_delete = [uuid for uuid in existing if uuid not in on_disk]
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
    )
