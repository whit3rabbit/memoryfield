"""`mf search` — dense-first retrieval with a calibrated confidence gate.

Ranking is dense's top-k (ROADMAP.md 2.6). Measured through this
pipeline on the cosine `vec` table, dense-first beat both FTS-first
(the 1.5 design) and RRF on every query set, in-vocabulary included:
codebase top-1 0.925 vs 0.828 vs 0.862 on the original set, 0.95 vs
0.70 vs 0.80 blind (`eval/calibrate_confidence_blind.py`). FTS still
runs on every query: its top score and top-1 are two of the three
gate signals (mf/confidence.py), and its ranked list is the result set
only when dense has nothing (an empty `vec` table).

A superseded page never occupies a result slot: it resolves to the page
that supersedes it (following the chain), and that stub carries a
`supersedes: [...]` list naming what it replaced (ROADMAP.md 2.8; the
1.5 design returned a `{uuid, superseded_by}` pointer in the slot, which
under `--limit 1` meant no answer at all).

Stale check (PLAN.md section 3, ROADMAP.md 2.8): when a `field_dir` is
given, every stub about to be shown has its file's sha256 compared to
the index. A mismatch or missing file raises StaleIndexError unless
`stale_ok`, in which case the stub is marked `stale`.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection

from . import embedder
from .confidence import Confidence, confidence
from .embedder import vec_literal
from .query_prep import fts_query
from .schema import DEFAULT_MODEL_CODE, get_config
from .tokens import default_tokenize

# Measured on the 1.9 tasks (eval/agent_trial_token_costs.py, output in
# eval/results/token_costs_2_11.txt): each stub is ~50 tokens and each
# neighbor slot roughly doubles the call. Old 5 / 3: 1009 tokens per
# lookup, 5.8x a raw file read. 3 / 1 (2.7's first pick): 304, still
# 1.75x raw. 2 / 0: 104, 0.6x raw. 1 / 0: 55, 0.32x. The answer was on
# screen at every setting, so neighbors bought nothing measurable there;
# two stubs keep one fallback for a wrong top-1 (dense top-1 is
# 0.90-0.95 on blind queries), and supersedes links already resolve
# inline. Neighbors are on demand (--neighbor-limit).
DEFAULT_LIMIT = 2
DEFAULT_NEIGHBOR_LIMIT = 0
_LINK_KINDS = ("supersedes", "contradicts", "depends_on")

MIN_CO_READ_WEIGHT = 2.0  # uncalibrated first cut: a pair must be read
# together at least twice before it counts as neighbor signal, not on
# the first incidental co-read. Same status as write.py's DEDUP_THRESHOLD
# pre-2.10: explicit, documented, not yet backed by a labeled set.


class StaleIndexError(RuntimeError):
    """A page about to be returned has changed on disk (or vanished)
    since `mf index` last saw it."""

    def __init__(self, stale: list[tuple[str, str]]):
        self.stale = stale
        listing = ", ".join(f"{uuid} ({filename})" for uuid, filename in stale)
        super().__init__(
            f"index is stale for {listing}; run `mf index` or pass --stale-ok"
        )


@dataclass
class Stub:
    uuid: str
    title: str = ""
    summary: str = ""
    status: str = "active"
    tokens: int = 0
    filename: str = ""
    sha256: str = ""
    supersedes: list[str] = field(default_factory=list)
    stale: bool = False
    neighbors: list[Stub] = field(default_factory=list)

    def as_dict(self) -> dict:
        d: dict = {
            "uuid": self.uuid, "title": self.title, "summary": self.summary,
            "status": self.status, "tokens": self.tokens,
        }
        if self.supersedes:
            d["supersedes"] = list(self.supersedes)
        if self.stale:
            d["stale"] = True
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


def _embed_query(query: str, model_code: str) -> list[float]:
    """Thin wrapper over mf.embedder so tests can monkeypatch the query
    path without loading a model."""
    return embedder.embed_query(query, model_code)


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
        (vec_literal(query_vector), limit),
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def _superseded_by(conn: Connection, uuid: str) -> str | None:
    row = conn.execute(
        "SELECT src FROM links WHERE dst = ? AND kind = 'supersedes' LIMIT 1", (uuid,)
    ).fetchone()
    return row[0] if row else None


def _load_stub(conn: Connection, uuid: str) -> Stub | None:
    row = conn.execute(
        "SELECT uuid, title, summary, status, tokens, filename, sha256 "
        "FROM pages WHERE uuid = ?", (uuid,)
    ).fetchone()
    if row is None:
        return None
    return Stub(uuid=row[0], title=row[1], summary=row[2], status=row[3],
                tokens=row[4], filename=row[5], sha256=row[6])


def _resolve_stub(conn: Connection, uuid: str) -> Stub | None:
    """The stub to show for `uuid`: itself, or whatever supersedes it
    (chain followed, cycle-guarded), annotated with what it replaced.
    A superseder that isn't indexed leaves the original in place."""
    chain: list[str] = []
    current = uuid
    while True:
        superseder = _superseded_by(conn, current)
        if not superseder or superseder in chain or superseder == uuid:
            break
        if _load_stub(conn, superseder) is None:
            break
        chain.append(current)
        current = superseder
    stub = _load_stub(conn, current)
    if stub is not None:
        stub.supersedes = chain
    return stub


def _neighbors(conn: Connection, uuid: str, limit: int) -> list[Stub]:
    if limit <= 0:
        return []
    neighbors: list[Stub] = []
    seen = {uuid}

    def _add(candidate: str) -> None:
        # `seen` tracks resolved uuids: a superseded candidate resolves to
        # its superseder, which may be the parent page itself or already
        # listed.
        stub = _resolve_stub(conn, candidate)
        if stub is None or stub.uuid in seen:
            return
        neighbors.append(stub)
        seen.add(stub.uuid)

    placeholders = ",".join("?" for _ in _LINK_KINDS)
    for row in conn.execute(
        f"SELECT dst FROM links WHERE src = ? AND kind IN ({placeholders})",
        (uuid, *_LINK_KINDS),
    ).fetchall():
        if len(neighbors) >= limit:
            break
        _add(row[0])

    if len(neighbors) < limit:
        for row in conn.execute(
            "SELECT dst, weight FROM links WHERE src = ? AND kind = 'co_read' "
            "UNION ALL "
            "SELECT src, weight FROM links WHERE dst = ? AND kind = 'co_read' "
            "ORDER BY weight DESC",
            (uuid, uuid),
        ).fetchall():
            if len(neighbors) >= limit:
                break
            if row[1] < MIN_CO_READ_WEIGHT:
                continue
            _add(row[0])

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
                _add(candidate[0])

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


def _mark_stale(field_dir: Path, stubs: list[Stub]) -> list[tuple[str, str]]:
    stale: list[tuple[str, str]] = []
    for stub in stubs:
        path = Path(stub.filename)
        if not path.is_absolute():
            path = field_dir / path
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            digest = ""
        if digest != stub.sha256:
            stub.stale = True
            stale.append((stub.uuid, stub.filename))
        stale.extend(_mark_stale(field_dir, stub.neighbors))
    return stale


def search(
    conn: Connection,
    query: str,
    limit: int = DEFAULT_LIMIT,
    neighbor_limit: int = DEFAULT_NEIGHBOR_LIMIT,
    budget: int | None = None,
    field_dir: Path | None = None,
    stale_ok: bool = False,
) -> SearchResult:
    """`field_dir` enables the stale check (compare each shown page's
    on-disk sha256 to the index); without it no check runs. `stale_ok`
    downgrades a stale hit from an error to a `stale: true` flag."""
    model_code = get_config(conn, "model_code") or DEFAULT_MODEL_CODE
    embedder.registry_entry(model_code)  # raises UnknownModelCodeError early

    fts_ranked, term_count = _fts_search(conn, query, limit)
    query_vector = _embed_query(query, model_code)
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
    shown: set[str] = set()
    for uuid in primary_uuids:
        stub = _resolve_stub(conn, uuid)
        if stub is None or stub.uuid in shown:
            continue  # two superseded hits can resolve to one superseder
        shown.add(stub.uuid)
        stub.neighbors = _neighbors(conn, stub.uuid, neighbor_limit)
        results.append(stub)

    result = SearchResult(confidence=conf, results=results)
    if budget is not None:
        _apply_budget(result, budget)
    if field_dir is not None:
        stale = _mark_stale(field_dir, result.results)
        if stale and not stale_ok:
            raise StaleIndexError(stale)
    return result
