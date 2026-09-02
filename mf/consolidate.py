"""`mf consolidate --plan` -- read `raw/`, search for matching pages,
emit a JSON plan of create/review actions with the evidence (ROADMAP.md
4.2).

PLAN.md's write layer: "`consolidate --plan` reads `raw/`, searches for
each candidate memory, and emits a JSON plan of create/update/supersede
actions with the evidence; the agent executes the plan with `write`."
The tool never calls an LLM (PLAN.md section 2), so this can only be
mechanical: embed each raw entry's text and kNN-search the field's
`vec` table the same way `write`'s dedup gate does, then report what it
found. It can't itself decide update vs supersede -- that's a judgment
about whether new information corrects or extends an existing page,
which needs a reader, not a distance. Anything with a candidate inside
`REVIEW_THRESHOLD` comes back as one `review` action (the raw text plus
the candidates, ranked); `create` means nothing existing looked
related. The host agent turns a `review` into `write --update UUID`
(extends or corrects that page) or a new page with `supersedes:
[UUID]` (replaces it), and a `create` into a fresh draft -- either way
through `write`, which is what actually gates and indexes.

Untuned by design, same shape as `write.py`'s `DEDUP_THRESHOLD` when it
first shipped (ROADMAP.md 2.1, calibrated for real only in 2.10 once a
labeled set existed): this reuses that same threshold as a first-cut
review/create boundary, since it's the only calibrated distance number
this codebase has. It has not been checked against real `raw/` entries,
because none exist yet -- that's 4.2's actual blocker (see ROADMAP.md).
Calibrating this against synthetic raw text would risk the exact
"calibrated where it couldn't matter" mistake CLAUDE.md warns about
(gotcha 36's family), so don't tighten this number without real data.

Not built: idempotency across repeated runs (nothing marks a `raw/`
entry as already planned, so the same entry shows up in every plan
until it's consolidated some other way) and expansion of session-end
pointer entries (`mf hook session-end`'s output has no prose to search
on, so a pointer is reported as its own `pointer` action instead of run
through the search -- someone still has to go read the transcript it
names).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection

from . import embedder
from .embedder import vec_literal
from .raw import RAW_DIRNAME
from .schema import DEFAULT_MODEL_CODE, get_config
from .write import DEDUP_THRESHOLD

REVIEW_THRESHOLD = DEDUP_THRESHOLD
REVIEW_CANDIDATES = 5
POINTER_MARKER = "kind: session-pointer"


@dataclass
class Candidate:
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
class ConsolidateAction:
    entry: str
    action: str  # "create" | "review" | "pointer"
    text: str
    candidates: list[Candidate] = field(default_factory=list)

    def as_dict(self) -> dict:
        d: dict = {"entry": self.entry, "action": self.action, "text": self.text}
        if self.candidates:
            d["candidates"] = [c.as_dict() for c in self.candidates]
        return d


@dataclass
class ConsolidatePlan:
    actions: list[ConsolidateAction] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"actions": [a.as_dict() for a in self.actions]}


def _raw_entries(field_dir: Path) -> list[Path]:
    raw_dir = field_dir / RAW_DIRNAME
    if not raw_dir.is_dir():
        return []
    return sorted(raw_dir.glob("*.md"))


def _find_candidates(
    conn: Connection, embedding: list[float], threshold: float, limit: int
) -> list[Candidate]:
    rows = conn.execute(
        "SELECT page_uuid, distance FROM vec WHERE embedding MATCH ? AND k = ?",
        (vec_literal(embedding), limit),
    ).fetchall()
    out: list[Candidate] = []
    for uuid, distance in rows:
        if distance is None or distance > threshold:
            continue
        row = conn.execute("SELECT title, summary FROM pages WHERE uuid = ?", (uuid,)).fetchone()
        if row is None:
            continue
        out.append(Candidate(uuid=uuid, title=row[0], summary=row[1], distance=distance))
    return out


def plan(
    field_dir: Path, conn: Connection, threshold: float = REVIEW_THRESHOLD
) -> ConsolidatePlan:
    """Read every `raw/` entry and propose create/review/pointer for it.
    Read-only: never writes to `raw/` or the index. The agent runs
    `write` to act on whatever this returns.
    """
    model_code = get_config(conn, "model_code") or DEFAULT_MODEL_CODE
    result = ConsolidatePlan()
    for entry in _raw_entries(field_dir):
        text = entry.read_text(encoding="utf-8").strip()
        rel = entry.relative_to(field_dir).as_posix()
        if text.startswith(POINTER_MARKER):
            result.actions.append(ConsolidateAction(entry=rel, action="pointer", text=text))
            continue
        embedding = embedder.embed_query(text, model_code)
        candidates = _find_candidates(conn, embedding, threshold, REVIEW_CANDIDATES)
        action = "review" if candidates else "create"
        result.actions.append(
            ConsolidateAction(entry=rel, action=action, text=text, candidates=candidates)
        )
    return result
