"""ROADMAP.md 1.9: the content-token half of the real-agent trial.

The trial itself (20 tasks x 2 conditions, real Claude subagents) isn't
scriptable -- it was run via the Agent tool and its results are written
up in eval/agent_trial_1_9.md. This script reproduces the one part of
it that IS deterministic and worth keeping runnable: the token cost of
what each condition's agent actually had in context when it answered,
using the real `mf search` pipeline (not mocked) against the same 20
codebase tasks.

The central finding this produced: `mf search`'s *default* flags
(--limit 5 --neighbor-limit 3) cost MORE than raw file exploration for
a single-answer point lookup, because every one of these 20 tasks was
answerable from the single top stub, yet the default renders 5 stubs
plus up to 3 neighbors each. A leaner call (--limit 1 --neighbor-limit
0) is the one that actually delivers the token savings PLAN.md section
6 modeled.

Usage: uv run python3 -m eval.agent_trial_token_costs
(needs a real mf.sqlite3 field built from eval/corpus/codebase --
pass --field to point at one, or it builds a throwaway one)
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from eval.mf_harness import load_queries
from mf import db, indexer
from mf.cli import _render_text
from mf.search import search
from mf.tokens import default_tokenize

ROOT = Path(__file__).parent
CORPUS_DIR = ROOT / "corpus" / "codebase"
QUERIES_BLIND_PATH = ROOT / "queries" / "codebase" / "queries_blind.jsonl"

# search() already routes queries through mf.embedder.embed_query, which
# has its own process-wide model cache keyed by model_code (mf/embedder.py
# _CACHE) -- an earlier version of this script re-implemented that caching
# itself via a monkeypatch, hardcoded to the nomic model regardless of
# which model the field was actually built with. That silently broke once
# the shipped default moved to snowflake-arctic-embed-xs (gotcha 38):
# querying a 384-d field with a 768-d nomic vector is a dimension
# mismatch, not just a wrong-model measurement.


def _load_tasks() -> list[tuple[str, str, list[str]]]:
    """(target uuid, question, extra raw files) tuples, sourced from
    eval/queries/codebase/queries_blind.jsonl rather than a second
    hand-maintained list: that file is already the field's blind,
    single-answer ground truth (ROADMAP.md 1.8's methodology), and a
    parallel list here duplicated the exact kind of source-of-truth
    ROADMAP.md already blames for the two biggest past bugs. Only
    single-answer entries whose target page exists in the corpus are
    usable (a raw-read baseline needs a real file); the four
    no-answer entries in that file are excluded. `extra` is always
    empty here -- the blind query set doesn't carry the "other files
    the trial's agent also opened" detail the original hand-written
    TASKS did (see eval/agent_trial_1_9.md for those transcripts)."""
    tasks = []
    for q in load_queries(QUERIES_BLIND_PATH, domain="codebase"):
        if len(q.answer_uuids) == 1 and (CORPUS_DIR / f"{q.answer_uuids[0]}.md").exists():
            tasks.append((q.answer_uuids[0], q.text, []))
    return tasks


TASKS = _load_tasks()


def _build_field() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="mf-agent-trial-"))
    for p in CORPUS_DIR.glob("*.md"):
        (tmp / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    db.init_field(tmp)
    conn = db.open_field(tmp)
    indexer.index_field(tmp, conn)
    conn.close()
    return tmp


def check_regression(conn, *, top1_floor: float = 0.9) -> tuple[bool, str]:
    """Assert the two invariants this script exists to catch: default
    `mf search` must not cost more tokens than reading the raw target
    file (the exact regression the pre-2.11 defaults shipped once
    already, CLAUDE.md gotcha 26), and lean top-1 correctness must not
    regress below `top1_floor`. Returns (ok, message)."""
    default_total = raw_total = 0
    top1_ok = 0
    n = len(TASKS)
    for uuid, question, extra in TASKS:
        r_default = search(conn, question)
        r_lean = search(conn, question, limit=1, neighbor_limit=0)
        default_total += default_tokenize(_render_text(r_default))
        if r_lean.results and r_lean.results[0].uuid == uuid:
            top1_ok += 1
        for f in [uuid, *extra]:
            raw_total += default_tokenize((CORPUS_DIR / f"{f}.md").read_text(encoding="utf-8"))

    top1_rate = top1_ok / n if n else 0.0
    problems = []
    if default_total > raw_total:
        problems.append(
            f"default mf search cost {default_total} tokens, more than "
            f"raw file reads at {raw_total} tokens"
        )
    if top1_rate < top1_floor:
        problems.append(
            f"lean top-1 correctness {top1_ok}/{n} ({top1_rate:.2f}) "
            f"is below the {top1_floor:.2f} floor"
        )
    return (not problems, "; ".join(problems))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--field", type=Path, default=None,
                         help="existing mf field (default: build a throwaway one)")
    parser.add_argument("--assert", dest="assert_regression", action="store_true",
                         help="exit 1 if check_regression() fails, after printing the report")
    args = parser.parse_args()

    owns_field = args.field is None
    field_dir = args.field or _build_field()
    conn = db.open_field(field_dir)

    # "old" = the 1.9-era defaults (5 / 3); "default" = whatever
    # mf/search.py's DEFAULT_LIMIT / DEFAULT_NEIGHBOR_LIMIT are now
    # (3 / 1 since ROADMAP.md 2.7); "lean" = the skill's point-lookup call.
    old_total = default_total = lean_total = raw_total = 0
    top1_ok = 0
    print(f"{'uuid':<32} {'old5/3':>7} {'default':>8} {'lean':>6} {'raw':>6}")
    for uuid, question, extra in TASKS:
        r_old = search(conn, question, limit=5, neighbor_limit=3)
        r_default = search(conn, question)
        r_lean = search(conn, question, limit=1, neighbor_limit=0)
        old_t = default_tokenize(_render_text(r_old))
        default_t = default_tokenize(_render_text(r_default))
        lean_t = default_tokenize(_render_text(r_lean))
        if r_lean.results and r_lean.results[0].uuid == uuid:
            top1_ok += 1

        raw_t = 0
        for f in [uuid, *extra]:
            raw_t += default_tokenize((CORPUS_DIR / f"{f}.md").read_text(encoding="utf-8"))

        old_total += old_t
        default_total += default_t
        lean_total += lean_t
        raw_total += raw_t
        print(f"{uuid:<32} {old_t:>7} {default_t:>8} {lean_t:>6} {raw_t:>6}")

    n = len(TASKS)
    print()
    print(f"{'TOTAL':<32} {old_total:>7} {default_total:>8} {lean_total:>6} {raw_total:>6}")
    print(f"{'avg/task':<32} {old_total/n:>7.1f} {default_total/n:>8.1f} {lean_total/n:>6.1f} {raw_total/n:>6.1f}")
    print(f"\nold 5/3 vs raw:  {old_total/raw_total:.2f}x")
    print(f"default vs raw:  {default_total/raw_total:.2f}x "
          f"({'mf costs more' if default_total > raw_total else 'mf costs less'})")
    print(f"lean vs raw:     {lean_total/raw_total:.2f}x "
          f"({'mf costs more' if lean_total > raw_total else 'mf costs less'})")
    print(f"lean top-1 correct: {top1_ok}/{n}")

    # Matrix over (limit, neighbor_limit) so the default is chosen on
    # numbers: avg tokens/task and how often the answer is on screen.
    print(f"\n{'limit/neighbors':<16} {'avg tokens':>10} {'vs raw':>7} {'answer shown':>13}")
    for limit in (1, 2, 3, 5):
        for nb in (0, 1, 3):
            total = shown = 0
            for uuid, question, _extra in TASKS:
                r = search(conn, question, limit=limit, neighbor_limit=nb)
                total += default_tokenize(_render_text(r))
                on_screen = {st.uuid for st in r.results} | {
                    nbr.uuid for st in r.results for nbr in st.neighbors
                }
                shown += uuid in on_screen
            print(f"{limit}/{nb:<14} {total/n:>10.1f} {total/raw_total:>6.2f}x {shown:>10}/{n}")

    ok, message = check_regression(conn)
    print(f"\ncheck_regression: {'PASS' if ok else 'FAIL'}" + (f" ({message})" if message else ""))

    conn.close()
    if owns_field:
        shutil.rmtree(field_dir, ignore_errors=True)
    return 0 if ok or not args.assert_regression else 1


if __name__ == "__main__":
    sys.exit(main())
