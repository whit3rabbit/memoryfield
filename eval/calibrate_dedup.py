"""ROADMAP.md 2.10: calibrate `mf/write.py`'s DEDUP_THRESHOLD on a labeled
near-duplicate set, through the real embedder and the cosine `vec` table.

The set (eval/dedup_set/<domain>/) was authored by subagents given only
the anchor page: for each anchor, `para-<anchor>.md` restates the same
facts in new wording (a duplicate the gate must block) and
`sib-<anchor>.md` answers a different question on the same topic (a
neighbor the gate must let through). Natural negatives come free: every
corpus page's nearest distinct neighbor is a pair the gate must not
block either.

For each threshold T the script reports the miss rate on paraphrases
(distance to their anchor > T, so they would be written as a second
page) and the false-block rate on siblings and corpus neighbors
(distance <= T). Output: eval/results/calibration_dedup_2_10.txt.

Run: uv run python3 -m eval.calibrate_dedup
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from mf import db, embedder, indexer
from mf.page import load_page

ROOT = Path(__file__).parent
CORPUS = ROOT / "corpus"
DEDUP_SET = ROOT / "dedup_set"
MODEL_CODE = "nomic-embed-text-v1.5"
THRESHOLDS = [round(0.02 * i, 2) for i in range(1, 13)]  # 0.02 .. 0.24


def _nearest(conn, vec: list[float], exclude: str | None = None, k: int = 2):
    rows = conn.execute(
        "SELECT page_uuid, distance FROM vec WHERE embedding MATCH ? AND k = ?",
        (embedder.vec_literal(vec), k),
    ).fetchall()
    return [(u, d) for u, d in rows if u != exclude]


def main() -> int:
    paras: list[tuple[str, str, float, bool]] = []   # (domain, uuid, dist_to_anchor, anchor_is_nearest)
    sibs: list[tuple[str, str, float, str]] = []     # (domain, uuid, nearest_dist, nearest_uuid)
    corpus_nn: list[tuple[str, str, float]] = []     # (domain, uuid, nearest_distinct_dist)
    corpus_pairs: list[tuple[float, str, str]] = []

    for domain in ("codebase", "papers"):
        tmp = Path(tempfile.mkdtemp(prefix=f"mf-dedup-{domain}-"))
        for p in (CORPUS / domain).glob("*.md"):
            shutil.copy(p, tmp / p.name)
        db.init_field(tmp)
        conn = db.open_field(tmp)
        indexer.index_field(tmp, conn)

        for u, in conn.execute("SELECT page_uuid FROM vec").fetchall():
            (emb,) = conn.execute("SELECT embedding FROM vec WHERE page_uuid = ?", (u,)).fetchone()
            rows = conn.execute(
                "SELECT page_uuid, distance FROM vec WHERE embedding MATCH ? AND k = 2", (emb,)
            ).fetchall()
            nearest_u, nearest_d = min(((pu, d) for pu, d in rows if pu != u), key=lambda x: x[1])
            corpus_nn.append((domain, u, nearest_d))
            corpus_pairs.append((nearest_d, u, nearest_u))

        set_dir = DEDUP_SET / domain
        for path in sorted(set_dir.glob("*.md")) if set_dir.exists() else []:
            page = load_page(path)
            vec = embedder.embed_page(page, MODEL_CODE)
            kind, _, anchor = page.uuid.partition("-")
            if kind == "para":
                (anchor_emb,) = conn.execute(
                    "SELECT embedding FROM vec WHERE page_uuid = ?", (anchor,)
                ).fetchone()
                # distance to the anchor specifically, plus whether it's the nearest
                nearest = _nearest(conn, vec, k=1)
                d_anchor = conn.execute(
                    "SELECT vec_distance_cosine(?, ?)", (embedder.vec_literal(vec), anchor_emb)
                ).fetchone()[0]
                paras.append((domain, page.uuid, d_anchor, bool(nearest) and nearest[0][0] == anchor))
            elif kind == "sib":
                nearest = _nearest(conn, vec, k=1)
                sibs.append((domain, page.uuid, nearest[0][1], nearest[0][0]))
        conn.close()
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"paraphrases: n={len(paras)}  siblings: n={len(sibs)}  corpus pages: n={len(corpus_nn)}")
    pd = sorted(d for _, _, d, _ in paras)
    sd = sorted(d for _, _, d, _ in sibs)
    cd = sorted(d for _, _, d in corpus_nn)
    def q(xs, f): return xs[min(len(xs) - 1, int(f * len(xs)))] if xs else float("nan")
    print(f"paraphrase->anchor distance: min={pd[0]:.3f} median={q(pd, .5):.3f} p90={q(pd, .9):.3f} max={pd[-1]:.3f}")
    print(f"  anchor was the nearest page for {sum(ok for *_, ok in paras)}/{len(paras)} paraphrases")
    print(f"sibling->nearest distance:   min={sd[0]:.3f} p10={q(sd, .1):.3f} median={q(sd, .5):.3f} max={sd[-1]:.3f}")
    print(f"corpus nearest-distinct:     min={cd[0]:.3f} p5={q(cd, .05):.3f} median={q(cd, .5):.3f}")
    print()
    print(f"{'T':>5} {'para miss':>10} {'sib block':>10} {'corpus block':>13}  {'errors':>6}")
    best: tuple[float, int] | None = None
    for t in THRESHOLDS:
        miss = sum(d > t for d in pd)
        sblock = sum(d <= t for d in sd)
        cblock = sum(d <= t for d in cd)
        errors = miss + sblock + cblock
        print(f"{t:>5.2f} {miss:>4}/{len(pd):<5} {sblock:>4}/{len(sd):<5} {cblock:>6}/{len(cd):<6} {errors:>6}")
        if best is None or errors < best[1]:
            best = (t, errors)
    if best is not None:
        print(f"\nlowest total error at T={best[0]:.2f} ({best[1]} errors)")
    print("\nparaphrases farthest from their anchor (hardest to catch):")
    for _domain, u, d, ok in sorted(paras, key=lambda x: -x[2])[:5]:
        print(f"  {d:.3f} {u} anchor_nearest={ok}")
    print("siblings closest to an existing page (hardest to let through):")
    for _domain, u, d, nu in sorted(sibs, key=lambda x: x[2])[:5]:
        print(f"  {d:.3f} {u} nearest={nu}")
    print("closest genuinely-different corpus pairs (what a higher T would block on write):")
    seen = set()
    for d, a, b in sorted(corpus_pairs):
        if (b, a) in seen or (a, b) in seen:
            continue
        seen.add((a, b))
        print(f"  {d:.3f} {a} <-> {b}")
        if len(seen) >= 8:
            break
    print(f"\ncurrent DEDUP_THRESHOLD = {__import__('mf.write', fromlist=['x']).DEDUP_THRESHOLD}")
    sys.stdout.flush()
    os._exit(0)  # onnxruntime teardown abort, CLAUDE.md gotcha 36


if __name__ == "__main__":
    sys.exit(main())
