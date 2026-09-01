"""Calibrate the FTS score gate's floor + relative-gap thresholds.

ROADMAP.md 1.4 / CLAUDE.md gotcha 15 / docs/architecture.md's "Confidence
gate" section: `search` needs to tell "no answer here" apart from "here's
an answer" using FTS's own bm25 scores, calibrated against the 30
no-answer queries embedded in the existing 458-query eval set.

This script only *measures* candidate gate designs -- it doesn't write
calibrated constants anywhere. See mf/confidence.py for the actual gate
function once a design is chosen.

sqlite's bm25() is lower-is-better and unbounded; we negate it so every
downstream comparison treats "higher score is better", matching the
cosine-similarity convention dense already uses.

First pass (raw bm25 floor) found no clean separation: no-answer and
real-answer-correct-hit score ranges overlap almost completely (see
CLAUDE.md gotcha 7 -- the query set shares an authoring process with the
corpus, so even "no answer" queries share vocabulary with some page).
Two follow-ups:
  1. Normalizing bm25 by the number of matched query terms, since raw
     magnitude mostly tracks query length/term rarity rather than match
     quality. This is what the "none vs. not-none" decision uses.
  2. An FTS/dense agreement signal: does nomic's top-1 pick agree with
     FTS's? A coincidental lexical match is unlikely to also be the
     nearest embedding (97.0% agreement on correct hits, 16.7% on
     no-answer queries). This is what the "high vs. low" decision uses.

Chosen design (mf/confidence.py): the combined gate, FLOOR=2.0.
0% false-high-confidence on the no-answer set, 19.8% of correct hits
demoted to "none" instead of returned. See CLAUDE.md gotcha 18 for a
scale-mismatch bug this script had mid-calibration, caught before the
number got hardcoded anywhere -- an earlier presented "0% false-high at
floor=1.5" was itself a bug artifact, not the real result.

Run: uv run python3 -m eval.calibrate_confidence
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from eval.baselines.dense_real_baseline import DenseIndex
from mf.query_prep import fts_query

from .mf_harness import Page, Query, load_corpus, load_queries

ROOT = Path(__file__).parent
CORPUS_DIR = ROOT / "corpus"
QUERIES_DIR = ROOT / "queries"

DOMAINS = {
    "codebase": ("codebase", "code"),
    "papers": ("papers", "papers"),
}


def _build_index(corpus: dict[str, Page]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE VIRTUAL TABLE pages USING fts5("
        "uuid UNINDEXED, title, summary, body, tokenize='porter ascii')"
    )
    conn.executemany(
        "INSERT INTO pages VALUES (?, ?, ?, ?)",
        [(p.uuid, p.title, p.summary, p.body) for p in corpus.values()],
    )
    return conn


def _scored_rank(conn: sqlite3.Connection, query: Query) -> tuple[list[tuple[str, float]], int]:
    """Top-10 (uuid, score) pairs (score = -bm25, higher is better) plus
    the number of query terms the FTS expression matched on.
    """
    parsed = fts_query(query.text)
    if not parsed.expr:
        return [], 0
    term_count = parsed.expr.count(" OR ") + 1
    try:
        cur = conn.execute(
            "SELECT uuid, -bm25(pages) AS score FROM pages "
            "WHERE pages MATCH ? ORDER BY score DESC LIMIT 10",
            (parsed.expr,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()], term_count
    except sqlite3.OperationalError:
        return [], term_count


@dataclass
class QuerySample:
    qid: str
    domain: str
    is_no_answer: bool
    top1_correct: bool  # meaningless when is_no_answer
    top_score: float | None
    second_score: float | None
    term_count: int
    dense_top1_uuid: str | None
    fts_top1_uuid: str | None

    @property
    def normalized_top_score(self) -> float | None:
        if self.top_score is None or self.term_count == 0:
            return None
        return self.top_score / self.term_count

    @property
    def fts_dense_agree(self) -> bool:
        return (
            self.fts_top1_uuid is not None
            and self.fts_top1_uuid == self.dense_top1_uuid
        )


def collect_samples() -> list[QuerySample]:
    samples: list[QuerySample] = []
    for domain_name, (corpus_dir, query_domain) in DOMAINS.items():
        corpus = load_corpus(CORPUS_DIR / corpus_dir)
        queries = load_queries(QUERIES_DIR / corpus_dir / "queries.jsonl", query_domain)
        conn = _build_index(corpus)

        dense_idx = DenseIndex("nomic-ai/nomic-embed-text-v1.5", "nomic")
        dense_idx.add_corpus(corpus)

        try:
            for q in queries:
                ranked, term_count = _scored_rank(conn, q)
                top_score = ranked[0][1] if ranked else None
                second_score = ranked[1][1] if len(ranked) > 1 else None
                fts_top1 = ranked[0][0] if ranked else None
                top1_correct = bool(ranked) and ranked[0][0] in q.answer_uuids

                dense_ranked = dense_idx.query(q.text, k=1)
                dense_top1 = dense_ranked[0][0] if dense_ranked else None

                samples.append(QuerySample(
                    qid=q.qid, domain=domain_name,
                    is_no_answer=(len(q.answer_uuids) == 0),
                    top1_correct=top1_correct,
                    top_score=top_score, second_score=second_score,
                    term_count=term_count,
                    dense_top1_uuid=dense_top1, fts_top1_uuid=fts_top1,
                ))
        finally:
            conn.close()
    return samples


def gate_floor(top_score: float | None, second_score: float | None,
                floor: float, gap: float) -> str:
    if top_score is None or top_score < floor:
        return "none"
    if second_score is not None:
        relative_gap = (top_score - second_score) / top_score
        if relative_gap < gap:
            return "low"
    return "high"


def gate_agreement(sample: QuerySample, floor: float) -> str:
    """confidence = high iff FTS and dense agree on the top-1 pick AND
    FTS's score clears a (much lower) floor; low if they disagree but
    FTS still found something; none if FTS found nothing above floor.
    """
    if sample.top_score is None or sample.top_score < floor:
        return "none"
    return "high" if sample.fts_dense_agree else "low"


def gate_combined(sample: QuerySample, floor: float) -> str:
    """none/not-none from the normalized-bm25 floor (the validated
    safety signal); high/low from FTS/dense agreement among whatever
    clears the floor (the validated confidence-quality signal). Two
    independently-calibrated signals, one per decision.
    """
    if sample.normalized_top_score is None or sample.normalized_top_score < floor:
        return "none"
    return "high" if sample.fts_dense_agree else "low"


def _split(samples: list[QuerySample]) -> tuple[list[QuerySample], list[QuerySample]]:
    no_answer = [s for s in samples if s.is_no_answer]
    correct_hits = [s for s in samples if not s.is_no_answer and s.top1_correct]
    return no_answer, correct_hits


def evaluate_floor(samples: list[QuerySample], floor: float, gap: float,
                    normalized: bool = False) -> dict:
    no_answer, correct_hits = _split(samples)

    def score_of(s: QuerySample) -> float | None:
        return s.normalized_top_score if normalized else s.top_score

    def second_of(s: QuerySample) -> float | None:
        if s.second_score is None:
            return None
        return s.second_score / s.term_count if normalized and s.term_count else s.second_score

    no_answer_calls = [gate_floor(score_of(s), second_of(s), floor, gap) for s in no_answer]
    hit_calls = [gate_floor(score_of(s), second_of(s), floor, gap) for s in correct_hits]
    return _report(floor, gap, no_answer_calls, hit_calls)


def evaluate_agreement(samples: list[QuerySample], floor: float) -> dict:
    no_answer, correct_hits = _split(samples)
    no_answer_calls = [gate_agreement(s, floor) for s in no_answer]
    hit_calls = [gate_agreement(s, floor) for s in correct_hits]
    return _report(floor, None, no_answer_calls, hit_calls)


def evaluate_combined(samples: list[QuerySample], floor: float) -> dict:
    no_answer, correct_hits = _split(samples)
    no_answer_calls = [gate_combined(s, floor) for s in no_answer]
    hit_calls = [gate_combined(s, floor) for s in correct_hits]
    return _report(floor, None, no_answer_calls, hit_calls)


def _report(floor, gap, no_answer_calls: list[str], hit_calls: list[str]) -> dict:
    # The dangerous failure: a no-answer query gets "high" (confidently
    # wrong). "low" on a no-answer query is the *correct* honest signal
    # (found a candidate, not sure), not a failure -- so it isn't counted
    # here, unlike the first-pass metric that conflated the two.
    false_high = sum(1 for c in no_answer_calls if c == "high")
    false_any = sum(1 for c in no_answer_calls if c != "none")
    suppressed = sum(1 for c in hit_calls if c == "none")
    lowered = sum(1 for c in hit_calls if c == "low")
    n_no_answer, n_hits = len(no_answer_calls), len(hit_calls)
    return {
        "floor": floor,
        "gap": gap,
        "false_high_rate": false_high / n_no_answer if n_no_answer else 0.0,
        "false_high_n": f"{false_high}/{n_no_answer}",
        "false_any_rate": false_any / n_no_answer if n_no_answer else 0.0,
        "false_any_n": f"{false_any}/{n_no_answer}",
        "suppressed_hit_rate": suppressed / n_hits if n_hits else 0.0,
        "suppressed_hit_n": f"{suppressed}/{n_hits}",
        "lowered_hit_rate": lowered / n_hits if n_hits else 0.0,
        "lowered_hit_n": f"{lowered}/{n_hits}",
    }


def _print_row(r: dict) -> None:
    gap_str = f"{r['gap']:.1f}" if r["gap"] is not None else "  - "
    print(f"{r['floor']:>6.1f} {gap_str:>5} "
          f"{r['false_high_rate']:.3f} ({r['false_high_n']:>6}) "
          f"{r['suppressed_hit_rate']:.3f} ({r['suppressed_hit_n']:>7}) "
          f"{r['lowered_hit_rate']:.3f} ({r['lowered_hit_n']:>7})")


def main() -> int:
    samples = collect_samples()
    no_answer, correct_hits = _split(samples)

    agree_rate_no_answer = sum(1 for s in no_answer if s.fts_dense_agree) / len(no_answer)
    agree_rate_correct = sum(1 for s in correct_hits if s.fts_dense_agree) / len(correct_hits)
    print(f"FTS/dense top-1 agreement on no-answer queries: {agree_rate_no_answer:.3f} "
          f"({sum(1 for s in no_answer if s.fts_dense_agree)}/{len(no_answer)})")
    print(f"FTS/dense top-1 agreement on correct-hit queries: {agree_rate_correct:.3f} "
          f"({sum(1 for s in correct_hits if s.fts_dense_agree)}/{len(correct_hits)})")
    print()

    print("=== Raw bm25 floor (baseline, for comparison) ===")
    print(f"{'floor':>6} {'gap':>5} {'false_high':>12} {'suppressed_hit':>16} {'lowered_hit':>13}")
    for floor in (7.0, 9.0, 11.0, 12.0):
        _print_row(evaluate_floor(samples, floor, 0.0))
    print()

    print("=== bm25 normalized by matched-term count ===")
    norm_scores_no_answer = sorted(
        s.normalized_top_score for s in no_answer if s.normalized_top_score is not None
    )
    norm_scores_correct = sorted(
        s.normalized_top_score for s in correct_hits if s.normalized_top_score is not None
    )
    print(f"no-answer normalized range: {norm_scores_no_answer[:3]} ... {norm_scores_no_answer[-3:]}")
    print(f"correct-hit normalized range: {norm_scores_correct[:3]} ... {norm_scores_correct[-3:]}")
    print(f"{'floor':>6} {'gap':>5} {'false_high':>12} {'suppressed_hit':>16} {'lowered_hit':>13}")
    for floor in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
        _print_row(evaluate_floor(samples, floor, 0.0, normalized=True))
    print()

    print("=== FTS/dense agreement gate (raw score floor) ===")
    print(f"{'floor':>6} {'gap':>5} {'false_high':>12} {'suppressed_hit':>16} {'lowered_hit':>13}")
    for floor in (0.0, 1.0, 3.0, 5.0, 7.0, 9.0, 11.0):
        _print_row(evaluate_agreement(samples, floor))
    print()

    print("=== Combined: normalized-bm25 floor (none) + agreement (high/low) ===")
    print(f"{'floor':>6} {'gap':>5} {'false_high':>12} {'suppressed_hit':>16} {'lowered_hit':>13}")
    for floor in (1.0, 1.3, 1.5, 2.0):
        _print_row(evaluate_combined(samples, floor))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
