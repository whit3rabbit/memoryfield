"""The search confidence gate: `confidence: high|low|none` per result set.

Calibrated (ROADMAP.md 1.4, CLAUDE.md gotcha 15/18) against the 30
no-answer queries embedded in the 458-query eval set. Two
independently-validated signals, one per decision:

  - none vs. not-none: FTS's bm25 score, normalized by the number of
    matched query terms. Raw bm25 magnitude alone does NOT separate
    no-answer from real-answer queries on this corpus (their score
    ranges overlap almost completely) -- it mostly tracks query
    length/term rarity, not match quality. Dividing by matched term
    count removes most of that confound.
  - high vs. low: does FTS's top-1 pick agree with dense's? Agreement
    is 97.0% on genuinely correct hits and only 16.7% on no-answer
    queries -- a coincidental lexical match is unlikely to also be the
    nearest embedding.

At FLOOR=2.0: 0% false-high-confidence on the 30-query no-answer set
(no no-answer query ever gets "high"), at the cost of 19.8% of
genuinely correct hits returning "none" instead of the right answer.
See eval/calibrate_confidence.py for the full trade-off table and
methodology; don't hand-copy more of that table here (CLAUDE.md's
no-duplication convention -- numbers there will move as future work
recalibrates, e.g. once 1.8's blind query set exists).
"""
from __future__ import annotations

from typing import Literal

Confidence = Literal["high", "low", "none"]

FLOOR = 2.0


def normalized_score(top_score: float, matched_term_count: int) -> float:
    """FTS top-1 score (higher is better), normalized by the number of
    matched query terms. This is what the gate's floor is calibrated
    against -- raw top_score alone is not comparable across queries.
    """
    if matched_term_count <= 0:
        raise ValueError("matched_term_count must be positive")
    return top_score / matched_term_count


def confidence(
    top_score: float | None,
    matched_term_count: int,
    fts_dense_agree: bool,
    floor: float = FLOOR,
) -> Confidence:
    """The calibrated confidence gate for a search result set.

    `top_score`: FTS's top-1 result score, higher-is-better convention
      (pass `-bm25(...)` for SQLite FTS5, which is lower-is-better and
      unbounded; see mf.query_prep for the query-side convention).
    `matched_term_count`: number of OR-joined terms in the FTS MATCH
      expression that produced `top_score` (`len(fts_query(q).expr.split(" OR "))`,
      or count the terms directly).
    `fts_dense_agree`: whether FTS's and dense's top-1 picks are the
      same page. Only consulted once the floor passes; a query with no
      FTS hit at all never reaches dense in the first place (FTS-first
      per docs/architecture.md), so pass `False` if dense wasn't run.
    `floor`: override for calibration/testing; production callers
      should use the default.
    """
    if top_score is None or matched_term_count <= 0:
        return "none"
    if normalized_score(top_score, matched_term_count) < floor:
        return "none"
    return "high" if fts_dense_agree else "low"
