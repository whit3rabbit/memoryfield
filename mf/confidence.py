"""The search confidence gate: `confidence: high|low|none` per result set.

Recalibrated (ROADMAP.md 2.7, `eval/calibrate_confidence_blind.py`) on
the blind vocabulary-mismatch sets, through the real pipeline on the
cosine `vec` table (ROADMAP.md 2.5), and swept across corpus sizes.
The 1.4 design (a normalized-bm25 floor deciding none vs. not-none,
FTS/dense top-1 agreement deciding high vs. low) had two problems the
blind sets exposed: 45% of answerable blind queries came back `none`,
and bm25's IDF term shrinks with corpus size so a 10-page field was
`none` for 80% of correct answers.

Three signals now, two decisions:

  not-none if ANY of:
    - normalized bm25 (FTS top score / matched-term count) >= FLOOR
      (keeps an exact-anchor lexical hit that dense misses)
    - dense top-1 cosine distance <= DENSE_FLOOR (corpus-size
      independent; this is what carries small fields)
    - FTS and dense agree on top-1 (two retrievers landing on the same
      page is itself evidence, whatever their scores)
  high if agree AND dense distance <= DENSE_FLOOR, else low.

At FLOOR=2.0, DENSE_FLOOR=0.30, presented result = dense top-1
("ok_cited" = presented top-1 correct and confidence not `none`):

                         in-vocabulary          blind
  codebase  ok_cited     0.920 (was 0.667)      0.900 (was 0.550)
            false-high   0/17                   1/24
            na not-none  5/17                   4/24
  papers    ok_cited     0.913 (was 0.728)      0.850 (was 0.550)
            false-high   0/13                   0/24
            na not-none  2/13                   4/24
  10-page subsample ok_cited: 0.889 / 1.000 (was 0.185 / 0.300)

The cost is the "na not-none" row: a no-answer query gets `low` (never
`high`, except the 1/24) 15-30% of the time instead of `none`. `low`
means "a lead, not an answer" (SKILL.md), which is the right label for
a topically-adjacent page. Full grid in eval/results/calibration_2_7.txt;
don't hand-copy more of it here.
"""
from __future__ import annotations

from typing import Literal

Confidence = Literal["high", "low", "none"]

FLOOR = 2.0
DENSE_FLOOR = 0.30


def normalized_score(top_score: float, matched_term_count: int) -> float:
    """FTS top-1 score (higher is better), normalized by the number of
    matched query terms. Raw top_score alone is not comparable across
    queries (it mostly tracks query length and term rarity).
    """
    if matched_term_count <= 0:
        raise ValueError("matched_term_count must be positive")
    return top_score / matched_term_count


def confidence(
    top_score: float | None,
    matched_term_count: int,
    fts_dense_agree: bool,
    dense_distance: float | None = None,
    floor: float = FLOOR,
    dense_floor: float = DENSE_FLOOR,
) -> Confidence:
    """The calibrated confidence gate for a search result set.

    `top_score`: FTS's top-1 result score, higher-is-better convention
      (pass `-bm25(...)` for SQLite FTS5), or None if FTS had no hit.
    `matched_term_count`: number of OR-joined terms in the FTS MATCH
      expression that produced `top_score`.
    `fts_dense_agree`: whether FTS's and dense's top-1 picks are the
      same page. False if either side had no result.
    `dense_distance`: cosine distance (1 - cos) of dense's top-1, or
      None if dense had no result.
    `floor`/`dense_floor`: overrides for calibration and tests;
      production callers use the defaults.
    """
    passes_fts = (
        top_score is not None
        and matched_term_count > 0
        and normalized_score(top_score, matched_term_count) >= floor
    )
    passes_dense = dense_distance is not None and dense_distance <= dense_floor
    if not (passes_fts or passes_dense or fts_dense_agree):
        return "none"
    return "high" if (fts_dense_agree and passes_dense) else "low"
