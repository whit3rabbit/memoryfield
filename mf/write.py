"""`mf write` -- validate, dedup-gate, and index a hand-authored page.

Per docs/architecture.md's "Write" layer (ROADMAP.md 2.1): a page is
still authored as a plain Markdown file on disk (`mf write` doesn't
create it -- an agent or human writes it first, following
`.claude/skills/mf/SKILL.md`'s conventions, same as before this
command existed). `write_page()` then validates it parses, runs the
dedup gate (dense similarity against every other page's embedding --
the `vec` table's second job, docs/architecture.md), and only indexes
it if the gate passes.

Dedup is deliberately a gate the tool enforces, not just an FYI: PLAN.md
section 10 calls it "an LLM judgment the tool can only inform," but the
gate still has to have an opinion about what counts as a candidate --
`--force`/`--update` are how the calling agent overrides that opinion
once it's made the actual judgment call.

DEDUP_THRESHOLD is cosine distance (1 - cos, ROADMAP.md 2.5; the `vec`
table's metric) and is still a first-cut estimate, not a calibrated
constant like mf/confidence.py's FLOOR. It was re-derived on the real
157-page corpus when the metric changed: see the DEDUP_THRESHOLD
comment below for the measured numbers. ROADMAP.md 2.10 builds a real
labeled near-duplicate set before trusting the exact number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection

from . import indexer
from .embedding import document_text
from .indexer import MODEL_REGISTRY, UnknownModelCodeError
from .page import Page, load_page
from .schema import DEFAULT_MODEL_CODE, get_config

# Cosine distance (1 - cos). Measured on the real 157-page corpus after
# the vec table moved to cosine (ROADMAP.md 2.5): two hand-written
# paraphrases of real pages landed at 0.038 and 0.063 from their
# originals, while the closest pair of genuinely different pages sat at
# 0.096 (papers, where sibling claim pages about one paper are near each
# other by design) and 0.131 (codebase). 0.08 splits that gap; the
# papers-side margin is thin, which is what ROADMAP.md 2.10's labeled
# set is for.
DEDUP_THRESHOLD = 0.08
DEDUP_CANDIDATES = 5


class WriteValidationError(ValueError):
    """Raised for input the dedup gate never gets to: a page path outside
    the field, or an --update uuid that doesn't match the page's own.
    """


@dataclass
class DedupCandidate:
    uuid: str
    title: str
    summary: str
    distance: float

    def as_dict(self) -> dict:
        return {
            "uuid": self.uuid, "title": self.title,
            "summary": self.summary, "distance": self.distance,
        }


@dataclass
class WriteResult:
    written: bool
    uuid: str = ""
    duplicates: list[DedupCandidate] = field(default_factory=list)

    def as_dict(self) -> dict:
        d: dict = {"written": self.written, "uuid": self.uuid}
        if self.duplicates:
            d["duplicates"] = [c.as_dict() for c in self.duplicates]
        return d


def _vec_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(v) for v in vector) + "]"


def _embed_page(page: Page, model_code: str) -> list[float]:
    if model_code not in MODEL_REGISTRY:
        raise UnknownModelCodeError(
            f"unknown model_code {model_code!r}; known: {list(MODEL_REGISTRY)}"
        )
    entry = MODEL_REGISTRY[model_code]
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=entry["fastembed_name"])
    text = document_text(page.title, page.summary, page.l1, entry["kind"])
    vec = next(iter(model.embed([text])))
    return [float(v) for v in vec]


def _find_duplicates(
    conn: Connection,
    embedding: list[float],
    exclude_uuid: str,
    threshold: float,
    limit: int,
) -> list[DedupCandidate]:
    # Over-fetch by one: exclude_uuid may itself be in `vec` already (a
    # page being re-written in place isn't a duplicate of itself).
    rows = conn.execute(
        "SELECT page_uuid, distance FROM vec WHERE embedding MATCH ? AND k = ?",
        (_vec_literal(embedding), limit + 1),
    ).fetchall()

    candidates: list[DedupCandidate] = []
    for uuid, distance in rows:
        # distance is NULL for a degenerate (zero) vector under cosine.
        if uuid == exclude_uuid or distance is None or distance > threshold:
            continue
        row = conn.execute(
            "SELECT title, summary FROM pages WHERE uuid = ?", (uuid,)
        ).fetchone()
        if row is None:
            continue
        candidates.append(DedupCandidate(uuid=uuid, title=row[0], summary=row[1], distance=distance))
        if len(candidates) >= limit:
            break
    return candidates


def write_page(
    field_dir: Path,
    conn: Connection,
    page_path: Path,
    update_uuid: str | None = None,
    force: bool = False,
    threshold: float = DEDUP_THRESHOLD,
) -> WriteResult:
    field_dir = field_dir.resolve()
    page_path = page_path.resolve()
    if field_dir not in page_path.parents:
        raise WriteValidationError(f"{page_path} is not inside field {field_dir}")

    page = load_page(page_path)  # raises PageParseError if invalid

    if update_uuid is not None and page.uuid != update_uuid:
        raise WriteValidationError(
            f"--update {update_uuid!r} doesn't match this page's own uuid {page.uuid!r}"
        )

    if not force and update_uuid is None:
        model_code = get_config(conn, "model_code") or DEFAULT_MODEL_CODE
        embedding = _embed_page(page, model_code)
        duplicates = _find_duplicates(
            conn, embedding, page.uuid, threshold, DEDUP_CANDIDATES
        )
        if duplicates:
            return WriteResult(written=False, uuid=page.uuid, duplicates=duplicates)

    indexer.index_field(field_dir, conn)
    return WriteResult(written=True, uuid=page.uuid)
