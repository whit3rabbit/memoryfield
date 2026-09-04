"""ROADMAP.md 2.7: recalibrate the confidence gate on realistic phrasing,
through the real `mf search` pipeline (cosine `vec`, ROADMAP.md 2.5),
not the eval harness's own dense index (CLAUDE.md gotcha 32).

Three questions, one script:

1. Gate designs. For every query in every set, record the raw signals
   the gate sees (FTS top score normalized by matched-term count, FTS
   top-1, dense top-1 and its cosine distance), then score candidate
   gate designs offline over a parameter grid:
     current       none if norm < F, else high if agree else low
     agree-rescues floor-fail but FTS/dense agree -> low, not none
     dense-floor   none if dense top-1 cosine distance > D (corpus-size
                   independent), else high if agree else low
     either        not-none if norm >= F or dense distance <= D
     combo         not-none if norm >= F or dense distance <= D or agree;
                   high only if agree AND dense distance <= D
   Reported per set: false-high and not-none rates on no-answer
   queries, `none` demotion and "ok_cited" (presented top-1 correct and
   confidence not none) on real-answer queries. Scored twice: with FTS's
   top-1 as the presented answer (as built) and with dense's (the 2.6
   candidate), since the low-confidence cases differ between the two.

2. Ranking (ROADMAP.md 2.6, same pass): top-1 accuracy and MRR@5 for
   FTS-first (as built), dense-first, and RRF (k=60, as
   eval/baselines/hybrid_baseline.py), per domain and set. The gate
   signals don't depend on which list is presented.

3. Corpus size. Subsample each corpus to N pages, keep the queries whose
   answers survived, and re-measure the current design at F=2.0 and the
   dense-floor design at a fixed D. bm25's IDF term shrinks with N, so
   the normalized-bm25 floor is expected to drift; a cosine floor should
   not.

Query sets: `queries.jsonl` (original, in-vocabulary, incl. the 30
no-answer queries the 1.4 calibration used), `queries_blind.jsonl`
(1.8, 40 real-answer + 8 no-answer), and `queries_blind_noanswer.jsonl`
(2.7, 40 more blind no-answer queries authored the same way as 1.8's).

Embedding model: the field's default (`mf.schema.DEFAULT_MODEL_CODE`,
arctic-xs since the model-management change) through `mf.embedder`, so
the numbers are the pipeline as shipped. `MF_CAL_MODEL=nomic-embed-text-v1.5`
reproduces the 2.7 run this script was written for (the gate constants
were calibrated on nomic; docs/architecture.md records that caveat).

Third domain (2026-09-02): `soapstones`, Cal Paterson's real 95-page
export, built from the fixture `eval/fetch_soapstones.py` downloads
(skipped when absent). Blind queries only (no in-vocabulary set exists
for it, and no size sweep: its uuids are not filename stems). A real
field with no writing discipline and `# Title` summaries, so this is a
stress test of the shipped pipeline, not a calibration set.

Run: uv run python3 -m eval.calibrate_confidence_blind [domain ...]
"""
from __future__ import annotations

import os
import random
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection

from eval.mf_harness import Query, load_queries
from mf import db, embedder, indexer, pack
from mf.confidence import Confidence
from mf.embedder import vec_literal
from mf.embedding import document_text
from mf.query_prep import fts_query
from mf.schema import DEFAULT_MODEL_CODE

ROOT = Path(__file__).parent
CORPUS_DIR = ROOT / "corpus"
QUERIES_DIR = ROOT / "queries"
DOMAINS = {"codebase": "code", "papers": "papers", "soapstones": "soap"}
# Domains built from a fetched spec archive instead of eval/corpus/.
FIXTURES = {"soapstones": ROOT / "fixtures" / "soapstones.memoryfield.zip"}
MODEL = os.environ.get("MF_CAL_MODEL", DEFAULT_MODEL_CODE)
MODEL_KIND = embedder.registry_entry(MODEL)["kind"]
MODEL_DIM = embedder.registry_entry(MODEL)["dim"]
SETS = {
    "original": "queries.jsonl",
    "blind": "queries_blind.jsonl",
    "blind_na": "queries_blind_noanswer.jsonl",
}
RRF_K = 60
TOPK = 5
FLOORS = [1.0, 1.5, 2.0, 2.5, 3.0]
DENSE_DISTS = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
SIZES = [10, 25, 50]

_PAGE_CACHE: dict[str, list[float]] = {}
_QUERY_CACHE: dict[str, list[float]] = {}


def _cached_embed_pages(pages, model_code):  # noqa: ARG001 -- monkeypatch target keeps the real signature
    missing = [p for p in pages if p.sha256 not in _PAGE_CACHE]
    if missing:
        texts = [document_text(p.title, p.summary, p.l1, MODEL_KIND) for p in missing]
        for p, v in zip(missing, embedder.embed_texts(texts, MODEL), strict=True):
            _PAGE_CACHE[p.sha256] = v
    return {p.uuid: _PAGE_CACHE[p.sha256] for p in pages}


def _embed_query(text: str) -> list[float]:
    if text not in _QUERY_CACHE:
        _QUERY_CACHE[text] = embedder.embed_query(text, MODEL)
    return _QUERY_CACHE[text]


@dataclass
class Obs:
    qid: str
    set_name: str
    answers: list[str]
    fts: list[tuple[str, float]]      # (uuid, -bm25) best first
    term_count: int
    dense: list[tuple[str, float]]    # (uuid, cosine distance) best first

    @property
    def real(self) -> bool:
        return bool(self.answers)

    @property
    def norm(self) -> float | None:
        if not self.fts or self.term_count <= 0:
            return None
        return self.fts[0][1] / self.term_count

    @property
    def fts_top1(self) -> str | None:
        return self.fts[0][0] if self.fts else None

    @property
    def dense_top1(self) -> str | None:
        return self.dense[0][0] if self.dense else None

    @property
    def dense_dist(self) -> float | None:
        return self.dense[0][1] if self.dense else None

    @property
    def agree(self) -> bool:
        return self.fts_top1 is not None and self.fts_top1 == self.dense_top1

    def ranked(self, how: str) -> list[str]:
        fts = [u for u, _ in self.fts]
        dense = [u for u, _ in self.dense]
        if how == "fts_first":
            return fts or dense
        if how == "dense_first":
            return dense
        if how == "dense_plus_fts1":
            # dense order, FTS's top-1 inserted at rank 2 when absent
            if fts and fts[0] not in dense:
                return [*dense[:1], fts[0], *dense[1:]]
            return dense
        fused: dict[str, float] = {}
        for lst in (fts, dense):
            for rank, u in enumerate(lst, start=1):
                fused[u] = fused.get(u, 0.0) + 1.0 / (RRF_K + rank)
        return sorted(fused, key=lambda u: -fused[u])


def _build_field(corpus_subdir: str, uuids: set[str] | None = None) -> tuple[Path, Connection]:
    tmp = Path(tempfile.mkdtemp(prefix=f"mf-cal-{corpus_subdir}-"))
    if corpus_subdir in FIXTURES:
        pack.unpack_field(FIXTURES[corpus_subdir], tmp, force=True)
    else:
        for p in (CORPUS_DIR / corpus_subdir).glob("*.md"):
            if uuids is None or p.stem in uuids:
                shutil.copy(p, tmp / p.name)
    db.init_field(tmp, MODEL, MODEL_DIM)
    conn = db.open_field(tmp)
    indexer.index_field(tmp, conn)
    return tmp, conn


def _observe(conn: Connection, q: Query, set_name: str) -> Obs:
    parsed = fts_query(q.text)
    fts: list = []
    term_count = 0
    if parsed.expr:
        term_count = parsed.expr.count(" OR ") + 1
        fts = conn.execute(
            "SELECT uuid, -bm25(fts) FROM fts WHERE fts MATCH ? ORDER BY 2 DESC LIMIT ?",
            (parsed.expr, TOPK),
        ).fetchall()
    dense = conn.execute(
        "SELECT page_uuid, distance FROM vec WHERE embedding MATCH ? AND k = ?",
        (vec_literal(_embed_query(q.text)), TOPK),
    ).fetchall()
    return Obs(q.qid, set_name, list(q.answer_uuids), [tuple(r) for r in fts],
               term_count, [tuple(r) for r in dense])


# ---- gate designs -------------------------------------------------------

def gate_current(o: Obs, F: float, D: float) -> Confidence:  # noqa: ARG001 -- uniform DESIGNS signature
    if o.norm is None or o.norm < F:
        return "none"
    return "high" if o.agree else "low"


def gate_agree_rescues(o: Obs, F: float, D: float) -> Confidence:  # noqa: ARG001 -- uniform DESIGNS signature
    if o.norm is None:
        return "none"
    if o.norm < F:
        return "low" if o.agree else "none"
    return "high" if o.agree else "low"


def gate_dense_floor(o: Obs, F: float, D: float) -> Confidence:  # noqa: ARG001 -- uniform DESIGNS signature
    if o.dense_dist is None or o.dense_dist > D:
        return "none"
    return "high" if o.agree else "low"


def gate_either(o: Obs, F: float, D: float) -> Confidence:
    passes_fts = o.norm is not None and o.norm >= F
    passes_dense = o.dense_dist is not None and o.dense_dist <= D
    if not (passes_fts or passes_dense):
        return "none"
    return "high" if o.agree else "low"


def gate_combo(o: Obs, F: float, D: float) -> Confidence:
    passes_fts = o.norm is not None and o.norm >= F
    passes_dense = o.dense_dist is not None and o.dense_dist <= D
    if not (passes_fts or passes_dense or o.agree):
        return "none"
    return "high" if (o.agree and passes_dense) else "low"


DESIGNS = {
    "current": gate_current,
    "agree-rescues": gate_agree_rescues,
    "dense-floor": gate_dense_floor,
    "either": gate_either,
    "combo": gate_combo,
}


def _rates(obs: list[Obs], gate, F: float, D: float, presented: str = "fts") -> dict[str, float | int]:
    na = [o for o in obs if not o.real]
    real = [o for o in obs if o.real]
    confs_na = [gate(o, F, D) for o in na]
    confs_real = [gate(o, F, D) for o in real]
    top1_ok = [
        (o.fts_top1 if presented == "fts" else o.dense_top1) in o.answers for o in real
    ]
    return {
        "n_na": len(na), "n_real": len(real),
        "na_high": sum(c == "high" for c in confs_na) / len(na) if na else 0.0,
        "na_notnone": sum(c != "none" for c in confs_na) / len(na) if na else 0.0,
        "real_none": sum(c == "none" for c in confs_real) / len(real) if real else 0.0,
        "real_ok_cited": sum(ok and c != "none" for ok, c in zip(top1_ok, confs_real, strict=True)) / len(real) if real else 0.0,
    }


def _fmt(r: dict) -> str:
    return (f"na_high={r['na_high']:.3f} na_notnone={r['na_notnone']:.3f} "
            f"real_none={r['real_none']:.3f} real_ok_cited={r['real_ok_cited']:.3f} "
            f"(n_na={r['n_na']} n_real={r['n_real']})")


def _ranking_table(obs: list[Obs], label: str) -> None:
    real = [o for o in obs if o.real]
    if not real:
        return
    print(f"  ranking, {label} (n={len(real)}):")
    for how in ("fts_first", "dense_first", "dense_plus_fts1", "rrf"):
        top1 = 0
        rr = 0.0
        for o in real:
            ranked = o.ranked(how)[:TOPK]
            if ranked and ranked[0] in o.answers:
                top1 += 1
            for i, u in enumerate(ranked, start=1):
                if u in o.answers:
                    rr += 1.0 / i
                    break
        print(f"    {how:<12} top1={top1/len(real):.3f} mrr@5={rr/len(real):.3f}")


def _wanted() -> dict[str, str]:
    """Domains to run: argv names, else all; fixture-backed ones only when
    the fixture has been fetched."""
    names = sys.argv[1:] or list(DOMAINS)
    unknown = [n for n in names if n not in DOMAINS]
    if unknown:
        sys.exit(f"unknown domain(s) {unknown}; known: {list(DOMAINS)}")
    out = {}
    for name in names:
        if name in FIXTURES and not FIXTURES[name].exists():
            print(f"[{name}] skipped: fixture missing, run `uv run python3 eval/fetch_soapstones.py`")
            continue
        out[name] = DOMAINS[name]
    return out


def main() -> int:
    indexer._embed_pages = _cached_embed_pages  # type: ignore[assignment]
    domains = _wanted()
    print(f"model={MODEL} ({MODEL_DIM}-d) domains={list(domains)}")
    all_obs: dict[str, list[Obs]] = {}
    for corpus_subdir, qdomain in domains.items():
        tmp, conn = _build_field(corpus_subdir)
        try:
            obs: list[Obs] = []
            for set_name, filename in SETS.items():
                path = QUERIES_DIR / corpus_subdir / filename
                if not path.exists():
                    continue
                for q in load_queries(path, qdomain):
                    obs.append(_observe(conn, q, set_name))
            all_obs[corpus_subdir] = obs
        finally:
            conn.close()
            shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 78)
    print("1. GATE DESIGNS, full corpus. Sets: original (in-vocabulary) vs blind.")
    print("   blind = queries_blind + queries_blind_noanswer")
    print("=" * 78)
    for corpus_subdir, obs in all_obs.items():
        orig = [o for o in obs if o.set_name == "original"]
        blind = [o for o in obs if o.set_name != "original"]
        print(f"\n[{corpus_subdir}]")
        for name, gate in DESIGNS.items():
            if name in ("current", "agree-rescues"):
                grid = [(F, 0.0) for F in FLOORS]
            elif name == "dense-floor":
                grid = [(0.0, D) for D in DENSE_DISTS]
            elif name == "either":
                grid = [(F, D) for F in (2.0, 2.5) for D in (0.25, 0.30)]
            else:
                grid = [(F, D) for F in (2.0, 2.5, 3.0) for D in (0.25, 0.30, 0.35)]
            for presented in ("fts", "dense"):
                print(f"  design={name} presented={presented}")
                for F, D in grid:
                    print(f"    F={F:<4} D={D:<5} original: {_fmt(_rates(orig, gate, F, D, presented))}")
                    print(f"    {'':<12} blind:    {_fmt(_rates(blind, gate, F, D, presented))}")

    print("\n" + "=" * 78)
    print("2. RANKING (ROADMAP.md 2.6): fts_first as built, dense_first, rrf k=60")
    print("=" * 78)
    for corpus_subdir, obs in all_obs.items():
        print(f"\n[{corpus_subdir}]")
        _ranking_table([o for o in obs if o.set_name == "original"], "original")
        _ranking_table([o for o in obs if o.set_name != "original"], "blind")

    print("\n" + "=" * 78)
    print("3. CORPUS SIZE SWEEP (seed 42), presented=dense")
    print("=" * 78)
    rng = random.Random(42)
    for corpus_subdir, qdomain in domains.items():
        if corpus_subdir in FIXTURES:
            print(f"\n[{corpus_subdir}] no size sweep: fixture uuids are not filename stems")
            continue
        all_uuids = sorted(p.stem for p in (CORPUS_DIR / corpus_subdir).glob("*.md"))
        queries: list[tuple[str, Query]] = []
        for set_name, filename in SETS.items():
            path = QUERIES_DIR / corpus_subdir / filename
            if path.exists():
                queries += [(set_name, q) for q in load_queries(path, qdomain)]
        print(f"\n[{corpus_subdir}] full={len(all_uuids)} pages")
        for n in [*SIZES, len(all_uuids)]:
            keep = set(rng.sample(all_uuids, n)) if n < len(all_uuids) else set(all_uuids)
            tmp, conn = _build_field(corpus_subdir, keep)
            try:
                obs = [
                    _observe(conn, q, s) for s, q in queries
                    if not q.answer_uuids or all(a in keep for a in q.answer_uuids)
                ]
            finally:
                conn.close()
                shutil.rmtree(tmp, ignore_errors=True)
            real = [o for o in obs if o.real]
            norms = sorted(o.norm for o in real if o.norm is not None and o.fts_top1 in o.answers)
            med = norms[len(norms) // 2] if norms else float("nan")
            print(f"  N={n:<4} n_real={len(real):<4} median norm(correct hits)={med:.2f}")
            for name, F, D in (
                ("current", 2.0, 0.0), ("agree-rescues", 2.0, 0.0),
                ("dense-floor", 0.0, 0.30), ("either", 2.0, 0.30),
                ("combo", 2.0, 0.25), ("combo", 2.0, 0.30), ("combo", 2.5, 0.30),
            ):
                print(f"    {name:<13} F={F:<4} D={D:<5} {_fmt(_rates(obs, DESIGNS[name], F, D, 'dense'))}")
    sys.stdout.flush()
    # fastembed/onnxruntime aborts with "recursive_mutex lock failed" while
    # tearing down the module-level model at interpreter exit (CLAUDE.md
    # gotcha 4's family). All output is flushed; skip the teardown.
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
