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

from . import schema
from .embedding import document_text
from .page import Page, PageParseError, load_page
from .tokens import default_tokenize

# Directories never walked looking for pages.
_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".mfgpt"}

# Spec model_code (docs/architecture.md, PLAN.md) -> fastembed registry name
# and the prefix "kind" mf/embedding.py's DOCUMENT_PREFIXES/QUERY_PREFIXES
# key on. Only nomic is wired: it's the spec default (PLAN.md's embedder
# table) and the only model init_field() currently configures.
MODEL_REGISTRY = {
    "nomic-embed-text-v1.5": {
        "fastembed_name": "nomic-ai/nomic-embed-text-v1.5",
        "kind": "nomic",
    },
}


class UnknownModelCodeError(ValueError):
    pass


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
    """
    pages: dict[str, Page] = {}
    for dirpath, dirnames, filenames in os.walk(field_dir):
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for name in fnmatch.filter(filenames, "*.md"):
            path = Path(dirpath) / name
            try:
                page = load_page(path)
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
    if not pages:
        return {}
    if model_code not in MODEL_REGISTRY:
        raise UnknownModelCodeError(
            f"unknown model_code {model_code!r}; known: {list(MODEL_REGISTRY)}"
        )
    entry = MODEL_REGISTRY[model_code]
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=entry["fastembed_name"])
    texts = [
        document_text(p.title, p.summary, p.l1, entry["kind"]) for p in pages
    ]
    vecs = list(model.embed(texts, batch_size=32))
    return {p.uuid: list(map(float, v)) for p, v in zip(pages, vecs)}


def _delete_page_rows(conn: sqlite3.Connection, uuid: str) -> None:
    conn.execute("DELETE FROM pages WHERE uuid = ?", (uuid,))
    conn.execute("DELETE FROM sections WHERE uuid = ?", (uuid,))
    conn.execute("DELETE FROM fts WHERE uuid = ?", (uuid,))
    conn.execute("DELETE FROM vec WHERE page_uuid = ?", (uuid,))
    conn.execute("DELETE FROM links WHERE src = ?", (uuid,))


def _write_page(
    conn: sqlite3.Connection, page: Page, embedding: list[float] | None
) -> None:
    _delete_page_rows(conn, page.uuid)

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
            (page.uuid, _vec_literal(embedding)),
        )

    for kind, targets in (
        ("supersedes", page.supersedes),
        ("contradicts", page.contradicts),
        ("depends_on", page.depends_on),
    ):
        for dst in targets:
            conn.execute(
                "INSERT OR REPLACE INTO links (src, dst, kind, weight) "
                "VALUES (?, ?, ?, 1.0)",
                (page.uuid, dst, kind),
            )


def _vec_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(v) for v in vector) + "]"


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
        _delete_page_rows(conn, uuid)
    for page in to_upsert:
        _write_page(conn, page, embeddings.get(page.uuid))

    conn.commit()
    return IndexResult(
        upserted=[p.uuid for p in to_upsert],
        deleted=to_delete,
        unchanged=unchanged,
    )
