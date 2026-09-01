"""ROADMAP.md 2.5: pin `mf/write.py`'s DEDUP_THRESHOLD in cosine distance.

Two numbers bound the threshold on the real corpus: the nearest
genuinely-different neighbor of every page (a threshold must stay
under the smallest of these, or real pages block each other) and the
distance of a hand-written paraphrase to its original (a threshold must
stay above these, or paraphrases sail through). Output is recorded in
eval/results/dedup_cosine_probe.txt. Not a labeled set (ROADMAP.md
2.10 builds that); two paraphrases and a nearest-neighbor floor.

Run: uv run python3 -m eval.dedup_cosine_probe
"""
from __future__ import annotations

import os
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

from mf import db, indexer, write
from mf.page import load_page

ROOT = Path(__file__).parent / "corpus"
MODEL_CODE = "nomic-embed-text-v1.5"

PARAPHRASES = {
    "codebase": {
        "para-rollback": """---
uuid: para-rollback
title: Rolling back a release that went bad
summary: Undo the deployment with `kubectl rollout undo deployment/<service>`. It rolls forward to the prior image and completes in about a minute and a half.
---
## Answer
Run `kubectl rollout undo deployment/<service>` to put the previous image back. Expect roughly 90 seconds for all pods to be replaced.
""",
        "para-401": """---
uuid: para-401
title: When to send 401 versus 403
summary: Send 401 when auth is missing or bad, 403 when auth is fine but the caller isn't allowed. Forbidden resources always get 403, never 404, so they can't be enumerated.
---
## Answer
401 means the request had no valid credentials. 403 means credentials were valid but the caller lacks permission. We never answer 404 for a forbidden resource.
""",
    },
    "papers": {},
}


def main() -> int:
    for domain in ("codebase", "papers"):
        tmp = Path(tempfile.mkdtemp(prefix=f"mf-dedup-{domain}-"))
        for p in (ROOT / domain).glob("*.md"):
            shutil.copy(p, tmp / p.name)
        db.init_field(tmp)
        conn = db.open_field(tmp)
        indexer.index_field(tmp, conn)
        uuids = [r[0] for r in conn.execute("SELECT page_uuid FROM vec")]
        nn = []
        for u in uuids:
            (emb,) = conn.execute("SELECT embedding FROM vec WHERE page_uuid = ?", (u,)).fetchone()
            rows = conn.execute(
                "SELECT page_uuid, distance FROM vec WHERE embedding MATCH ? AND k = 2", (emb,)
            ).fetchall()
            nn.append(min(d for pu, d in rows if pu != u))
        nn.sort()
        print(f"{domain}: n={len(nn)} nearest-distinct-neighbor cosine distance: "
              f"min={nn[0]:.3f} p5={nn[len(nn) // 20]:.3f} p25={nn[len(nn) // 4]:.3f} "
              f"median={statistics.median(nn):.3f}")
        print("  5 closest:", [f"{d:.3f}" for d in nn[:5]])
        for pu, text in PARAPHRASES[domain].items():
            path = tmp / f"{pu}.md"
            path.write_text(text)
            emb = write._embed_page(load_page(path), MODEL_CODE)
            rows = conn.execute(
                "SELECT page_uuid, distance FROM vec WHERE embedding MATCH ? AND k = 3",
                (write._vec_literal(emb),),
            ).fetchall()
            print(f"  paraphrase {pu}:", [(r[0], round(r[1], 3)) for r in rows])
        conn.close()
        shutil.rmtree(tmp)
    print(f"DEDUP_THRESHOLD = {write.DEDUP_THRESHOLD}")
    sys.stdout.flush()
    os._exit(0)  # onnxruntime teardown abort, CLAUDE.md gotcha 36


if __name__ == "__main__":
    sys.exit(main())
