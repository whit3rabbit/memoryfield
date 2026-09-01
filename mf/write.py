"""`mf write` -- validate, dedup-gate, place, and index a page.

Per docs/architecture.md's "Write" layer (ROADMAP.md 2.1, reshaped by
2.8). The draft can come from anywhere: a path outside the field, a
path inside it, or stdin. Only a draft that passes validation and the
dedup gate is written into the field, and only that page is indexed.

Why the draft should be outside the field (2.8): the gate can only
refuse to *index*. A blocked draft that already sits inside the field
is still a `.md` with valid frontmatter, so the next `mf index` picks
it up with no check at all. Drafting outside the field and letting
`write` copy it in on a pass is what makes the gate a gate. An in-field
draft still works (it's how 2.1 shipped) and the result carries a
warning saying exactly that.

Dedup is deliberately a gate the tool enforces, not just an FYI: PLAN.md
section 10 calls it "an LLM judgment the tool can only inform," but the
gate still has to have an opinion about what counts as a candidate --
`--force`/`--update` are how the calling agent overrides that opinion
once it's made the actual judgment call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection

from . import indexer
from .embedding import document_text
from .indexer import MODEL_REGISTRY, UnknownModelCodeError
from .page import Page, load_page, parse_page
from .schema import DEFAULT_MODEL_CODE, get_config

# Cosine distance (1 - cos). Measured on the real 157-page corpus after
# the vec table moved to cosine (ROADMAP.md 2.5, eval/dedup_cosine_probe.py):
# two hand-written paraphrases of real pages landed at 0.038 and 0.063
# from their originals, while the closest pair of genuinely different
# pages sat at 0.096 (papers, where sibling claim pages about one paper
# are near each other by design) and 0.131 (codebase). 0.08 splits that
# gap; the papers-side margin is thin, which is what ROADMAP.md 2.10's
# labeled set is for.
DEDUP_THRESHOLD = 0.08
DEDUP_CANDIDATES = 5

IN_FIELD_WARNING = (
    "draft is inside the field: the dedup gate blocked indexing it, but the "
    "file is still there and the next `mf index` will index it unchecked. "
    "Move or delete it, or draft outside the field next time."
)


class WriteValidationError(ValueError):
    """Raised for input the dedup gate never gets to: a bad destination,
    an --update uuid that doesn't match the page's own, a uuid already
    indexed under another filename.
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
    path: str = ""
    duplicates: list[DedupCandidate] = field(default_factory=list)
    warning: str | None = None

    def as_dict(self) -> dict:
        d: dict = {"written": self.written, "uuid": self.uuid}
        if self.path:
            d["path"] = self.path
        if self.duplicates:
            d["duplicates"] = [c.as_dict() for c in self.duplicates]
        if self.warning:
            d["warning"] = self.warning
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


def _check_destination(field_dir: Path, conn: Connection, page: Page, dest: Path) -> None:
    rel = dest.relative_to(field_dir).as_posix()
    if dest.exists():
        existing = load_page(dest)
        if existing.uuid != page.uuid:
            raise WriteValidationError(
                f"{rel} already exists with a different uuid ({existing.uuid!r}); "
                "pick another --dest or update that page instead"
            )
    row = conn.execute("SELECT filename FROM pages WHERE uuid = ?", (page.uuid,)).fetchone()
    if row is not None and row[0] != rel:
        raise WriteValidationError(
            f"uuid {page.uuid!r} is already indexed at {row[0]}; write to that "
            "path (or pass it as --dest) rather than creating a second file"
        )


def _commit(
    field_dir: Path,
    conn: Connection,
    page: Page,
    text: str,
    dest: Path,
    in_field_source: bool,
    update_uuid: str | None,
    force: bool,
    threshold: float,
) -> WriteResult:
    if update_uuid is not None and page.uuid != update_uuid:
        raise WriteValidationError(
            f"--update {update_uuid!r} doesn't match this page's own uuid {page.uuid!r}"
        )
    _check_destination(field_dir, conn, page, dest)

    if not force and update_uuid is None:
        model_code = get_config(conn, "model_code") or DEFAULT_MODEL_CODE
        embedding = _embed_page(page, model_code)
        duplicates = _find_duplicates(
            conn, embedding, page.uuid, threshold, DEDUP_CANDIDATES
        )
        if duplicates:
            return WriteResult(
                written=False, uuid=page.uuid, duplicates=duplicates,
                warning=IN_FIELD_WARNING if in_field_source else None,
            )

    if not in_field_source:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    indexer.index_page(field_dir, conn, dest)
    return WriteResult(written=True, uuid=page.uuid, path=dest.relative_to(field_dir).as_posix())


def write_page(
    field_dir: Path,
    conn: Connection,
    page_path: Path,
    update_uuid: str | None = None,
    force: bool = False,
    threshold: float = DEDUP_THRESHOLD,
    dest_name: str | None = None,
) -> WriteResult:
    """Validate, gate, and index the page at `page_path`. A path outside
    the field is a draft: copied to `field_dir / dest_name` (default:
    the draft's own filename) only on a pass. A path inside the field is
    validated and indexed in place.
    """
    field_dir = field_dir.resolve()
    page_path = page_path.resolve()
    in_field = field_dir in page_path.parents
    if in_field and dest_name is not None:
        raise WriteValidationError("--dest only applies to a draft outside the field")

    text = page_path.read_text(encoding="utf-8")
    page = parse_page(text, filename=str(page_path))  # raises PageParseError
    dest = page_path if in_field else field_dir / (dest_name or page_path.name)
    return _commit(field_dir, conn, page, text, dest, in_field, update_uuid, force, threshold)


def write_text(
    field_dir: Path,
    conn: Connection,
    text: str,
    dest_name: str,
    update_uuid: str | None = None,
    force: bool = False,
    threshold: float = DEDUP_THRESHOLD,
) -> WriteResult:
    """Same as write_page() for a draft that only exists as text (stdin)."""
    field_dir = field_dir.resolve()
    page = parse_page(text, filename=dest_name)
    dest = (field_dir / dest_name).resolve()
    if field_dir not in dest.parents:
        raise WriteValidationError(f"--dest {dest_name!r} escapes the field directory")
    return _commit(field_dir, conn, page, text, dest, False, update_uuid, force, threshold)
