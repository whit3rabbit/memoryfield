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

from mf import db, indexer
from mf import search as search_mod
from mf.cli import _render_text
from mf.embedding import query_text
from mf.search import search
from mf.tokens import default_tokenize

ROOT = Path(__file__).parent
CORPUS_DIR = ROOT / "corpus" / "codebase"

_MODEL_CACHE: dict = {}


def _cached_embed_query(query: str, model_kind: str, model_name: str) -> list[float]:
    if model_name not in _MODEL_CACHE:
        from fastembed import TextEmbedding
        _MODEL_CACHE[model_name] = TextEmbedding(model_name=model_name)
    model = _MODEL_CACHE[model_name]
    vec = next(iter(model.embed([query_text(query, model_kind)])))
    return [float(v) for v in vec]


# (target uuid, question, extra raw files the trial's agent actually read
# beyond the target -- see eval/agent_trial_1_9.md for the transcripts)
TASKS = [
    ("code-api-webhook-sig", "How do we verify the signature on an incoming webhook request?", []),
    ("code-api-pagination", "How does pagination work on the GET /users endpoint?", []),
    ("code-auth-s2s-tokens", "How do two internal services authenticate to each other?", ["code-auth-user-vs-service-jwt"]),
    ("code-auth-ed25519-vs-rsa", "Why do we sign tokens with Ed25519 instead of RSA?", []),
    ("code-auth-public-keys", "Where are the public keys used to verify our JWTs stored?", []),
    ("code-billing-stripe-webhook", "How do we verify a Stripe webhook is legitimate?", []),
    ("code-billing-proration-edge", "What happens to a billing line that starts or ends exactly on a period boundary?", ["code-billing-line-math"]),
    ("code-billing-trial", "How are trial periods represented on an invoice?", []),
    ("code-deploy-immutable-tags", "Why do we use immutable image tags for deploys?", []),
    ("code-deploy-stuck-rollout", "A deploy rollout seems stuck. How do I debug that?", []),
    ("code-deploy-pdb", "What's a pod disruption budget and how does it protect our deploys?", []),
    ("code-dm-no-fk", "Why don't we use foreign key constraints in the database?", []),
    ("code-dm-timestamptz", "What column type should I use for a time field in the database?", []),
    ("code-migrations-rename-column", "What's the safe process for renaming a database column?", []),
    ("code-migrations-online-offline", "What's the difference between an online and offline schema migration?", []),
    ("code-migrations-rollback", "How do I roll back a migration that was already applied?", []),
    ("code-obs-error-budget", "What's the error budget used for?", []),
    ("code-obs-oncall-rotation", "How does the on-call rotation work?", []),
    ("code-testing-coverage-gate", "What's the required code coverage for a PR?", []),
    ("code-testing-integration-org", "How are integration tests organized and run?", []),
]


def _build_field() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="mf-agent-trial-"))
    for p in CORPUS_DIR.glob("*.md"):
        (tmp / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    db.init_field(tmp)
    conn = db.open_field(tmp)
    indexer.index_field(tmp, conn)
    conn.close()
    return tmp


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--field", type=Path, default=None,
                         help="existing mf field (default: build a throwaway one)")
    args = parser.parse_args()

    search_mod._embed_query = _cached_embed_query

    owns_field = args.field is None
    field_dir = args.field or _build_field()
    conn = db.open_field(field_dir)

    default_total = lean_total = raw_total = 0
    print(f"{'uuid':<32} {'default':>8} {'lean':>6} {'raw':>6}")
    for uuid, question, extra in TASKS:
        r_default = search(conn, question, limit=5, neighbor_limit=3)
        r_lean = search(conn, question, limit=1, neighbor_limit=0)
        default_t = default_tokenize(_render_text(r_default))
        lean_t = default_tokenize(_render_text(r_lean))

        raw_t = 0
        for f in [uuid, *extra]:
            raw_t += default_tokenize((CORPUS_DIR / f"{f}.md").read_text(encoding="utf-8"))

        default_total += default_t
        lean_total += lean_t
        raw_total += raw_t
        print(f"{uuid:<32} {default_t:>8} {lean_t:>6} {raw_t:>6}")

    n = len(TASKS)
    print()
    print(f"{'TOTAL':<32} {default_total:>8} {lean_total:>6} {raw_total:>6}")
    print(f"{'avg/task':<32} {default_total/n:>8.1f} {lean_total/n:>6.1f} {raw_total/n:>6.1f}")
    print(f"\ndefault vs raw: {default_total/raw_total:.2f}x "
          f"({'mf costs more' if default_total > raw_total else 'mf costs less'})")
    print(f"lean vs raw:    {lean_total/raw_total:.2f}x "
          f"({'mf costs more' if lean_total > raw_total else 'mf costs less'})")

    conn.close()
    if owns_field:
        shutil.rmtree(field_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
