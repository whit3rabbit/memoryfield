"""`mf search` — dense-first retrieval with a calibrated confidence gate.

Ranking is dense's top-k (ROADMAP.md 2.6). Measured through this
pipeline on the cosine `vec` table, dense-first beat both FTS-first
(the 1.5 design) and RRF on every query set, in-vocabulary included:
codebase top-1 0.925 vs 0.828 vs 0.862 on the original set, 0.95 vs
0.70 vs 0.80 blind (`eval/calibrate_confidence_blind.py`). FTS still
runs on every query: its top score and top-1 are two of the three
gate signals (mf/confidence.py), and its ranked list is the result set
only when dense has nothing (an empty `vec` table).

A superseded page never appears as a full stub in results -- it folds
into a compact `{uuid, superseded_by}` pointer (docs/architecture.md
"Retrieval", point 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from sqlite3 import Connection

from .confidence import Confidence, confidence
from .embedding import query_text
from .indexer import MODEL_REGISTRY, UnknownModelCodeError
from .query_prep import fts_query
from .schema import DEFAULT_MODEL_CODE, get_config
from .tokens import default_tokenize

# ROADMAP.md 1.9 measured the old defaults (5 / 3) at 1014 tokens per
# point lookup, 5.85x a raw file read; the skill's lean call (1 / 0) at
# 55. 3 / 1 is the compromise chosen with the 2.7 recalibration: three
# stubs recover from a wrong top-1 (dense top-1 is 0.90-0.95 on blind
# queries), and one neighbor slot is enough to surface a typed
# supersedes/contradicts link, which is the neighbor kind an agent must
# not miss. Typed links rank before kNN in _neighbors().
DEFAULT_LIMIT = 3
DEFAULT_NEIGHBOR_LIMIT = 1
_LINK_KINDS = ("supersedes", "contradicts", "depends_on")


@dataclass
class Stub:
    uuid: str
    title: str = ""
    summary: str = ""
    status: str = "active"
    tokens: int = 0
    superseded_by: str | None = None
    neighbors: list[Stub] = field(default_factory=list)

    def as_dict(self) -> dict:
        if self.superseded_by:
            return {"uuid": self.uuid, "superseded_by": self.superseded_by}
        d: dict = {
            "uuid": self.uuid, "title": self.title, "summary": self.summary,
            "status": self.status, "tokens": self.tokens,
        }
        if self.neighbors:
            d["neighbors"] = [n.as_dict() for n in self.neighbors]
        return d


@dataclass
class SearchResult:
    confidence: Confidence
    results: list[Stub]

    def as_dict(self) -> dict:
        return {
            "confidence": self.confidence,
            "results": [r.as_dict() for r in self.results],
        }


def _vec_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(v) for v in vector) + "]"


def _embed_query(query: str, model_kind: str, model_name: str) -> list[float]:
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=model_name)
    vec = next(iter(model.embed([query_text(query, model_kind)])))
    return [float(v) for v in vec]


def _fts_search(conn: Connection, query: str, limit: int) -> tuple[list[tuple[str, float]], int]:
    """Top-`limit` (uuid, score) pairs, score = -bm25 (higher is better),
    plus the number of matched query terms (mf.confidence's normalizer).
    """
    parsed = fts_query(query)
    if not parsed.expr:
        return [], 0
    term_count = parsed.expr.count(" OR ") + 1
    cur = conn.execute(
        "SELECT uuid, -bm25(fts) AS score FROM fts WHERE fts MATCH ? "
        "ORDER BY score DESC LIMIT ?",
        (parsed.expr, limit),
    )
    return [(row[0], row[1]) for row in cur.fetchall()], term_count


def _dense_search(
    conn: Connection, query_vector: list[float], limit: int
) -> list[tuple[str, float]]:
    """Top-`limit` (uuid, cosine distance) pairs, nearest first."""
    cur = conn.execute(
        "SELECT page_uuid, distance FROM vec WHERE embedding MATCH ? AND k = ?",
        (_vec_literal(query_vector), limit),
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def _superseded_by(conn: Connection, uuid: str) -> str | None:
    row = conn.execute(
        "SELECT src FROM links WHERE dst = ? AND kind = 'supersedes' LIMIT 1", (uuid,)
    ).fetchone()
    return row[0] if row else None


def _load_stub(conn: Connection, uuid: str) -> Stub | None:
    row = conn.execute(
        "SELECT uuid, title, summary, status, tokens FROM pages WHERE uuid = ?", (uuid,)
    ).fetchone()
    if row is None:
        return None
    return Stub(uuid=row[0], title=row[1], summary=row[2], status=row[3], tokens=row[4])


def _resolve_stub(conn: Connection, uuid: str) -> Stub | None:
    superseder = _superseded_by(conn, uuid)
    if superseder:
        return Stub(uuid=uuid, superseded_by=superseder)
    return _load_stub(conn, uuid)


def _neighbors(conn: Connection, uuid: str, limit: int) -> list[Stub]:
    if limit <= 0:
        return []
    neighbors: list[Stub] = []
    seen = {uuid}

    placeholders = ",".join("?" for _ in _LINK_KINDS)
    for row in conn.execute(
        f"SELECT dst FROM links WHERE src = ? AND kind IN ({placeholders})",
        (uuid, *_LINK_KINDS),
    ).fetchall():
        if len(neighbors) >= limit:
            break
        if row[0] in seen:
            continue
        stub = _resolve_stub(conn, row[0])
        if stub:
            neighbors.append(stub)
            seen.add(row[0])

    if len(neighbors) < limit:
        vec_row = conn.execute(
            "SELECT embedding FROM vec WHERE page_uuid = ?", (uuid,)
        ).fetchone()
        if vec_row:
            # Over-fetch so self and already-seen typed-link targets can
            # be skipped without under-filling.
            k = limit + len(seen)
            for candidate in conn.execute(
                "SELECT page_uuid FROM vec WHERE embedding MATCH ? AND k = ?",
                (vec_row[0], k),
            ).fetchall():
                if len(neighbors) >= limit:
                    break
                if candidate[0] in seen:
                    continue
                stub = _resolve_stub(conn, candidate[0])
                if stub:
                    neighbors.append(stub)
                    seen.add(candidate[0])

    # co_read rows exist (mf read populates them, ROADMAP.md 1.6) but
    # aren't consulted for neighbor ranking yet -- that's ROADMAP.md 4.4,
    # gated on enough signal accumulating. Documented no-op, not a
    # missing feature masquerading as done.
    return neighbors


def _stub_cost(stub: Stub) -> int:
    return default_tokenize(f"- [{stub.uuid}] {stub.title}\n    {stub.summary}")


def _apply_budget(result: SearchResult, budget: int) -> None:
    used = 0
    kept: list[Stub] = []
    for stub in result.results:
        cost = _stub_cost(stub)
        neighbor_costs = [_stub_cost(n) for n in stub.neighbors]
        if used + cost + sum(neighbor_costs) <= budget:
            used += cost + sum(neighbor_costs)
            kept.append(stub)
            continue
        if used + cost <= budget:
            # Stub fits, its neighbors don't -- keep the stub, drop
            # neighbors rather than dropping a real result over its
            # extras.
            stub.neighbors = []
            used += cost
            kept.append(stub)
            continue
        break
    result.results = kept


def search(
    conn: Connection,
    query: str,
    limit: int = DEFAULT_LIMIT,
    neighbor_limit: int = DEFAULT_NEIGHBOR_LIMIT,
    budget: int | None = None,
) -> SearchResult:
    model_code = get_config(conn, "model_code") or DEFAULT_MODEL_CODE
    if model_code not in MODEL_REGISTRY:
        raise UnknownModelCodeError(
            f"unknown model_code {model_code!r}; known: {list(MODEL_REGISTRY)}"
        )
    entry = MODEL_REGISTRY[model_code]

    fts_ranked, term_count = _fts_search(conn, query, limit)
    query_vector = _embed_query(query, entry["kind"], entry["fastembed_name"])
    dense_ranked = _dense_search(conn, query_vector, limit)

    fts_top1 = fts_ranked[0][0] if fts_ranked else None
    top_score = fts_ranked[0][1] if fts_ranked else None
    dense_top1 = dense_ranked[0][0] if dense_ranked else None
    dense_distance = dense_ranked[0][1] if dense_ranked else None
    agree = fts_top1 is not None and fts_top1 == dense_top1
    conf = confidence(top_score, term_count, agree, dense_distance)

    if dense_ranked:
        primary_uuids = [uuid for uuid, _ in dense_ranked]
    else:
        primary_uuids = [uuid for uuid, _ in fts_ranked]

    results: list[Stub] = []
    for uuid in primary_uuids:
        stub = _resolve_stub(conn, uuid)
        if stub is None:
            continue
        if stub.superseded_by is None:
            stub.neighbors = _neighbors(conn, uuid, neighbor_limit)
        results.append(stub)

    result = SearchResult(confidence=conf, results=results)
    if budget is not None:
        _apply_budget(result, budget)
    return result
