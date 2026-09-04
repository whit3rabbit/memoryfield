"""Guards the two invariants eval/agent_trial_token_costs.py exists to
catch (CLAUDE.md gotcha 26): default `mf search` must not cost more
tokens than reading the raw target file, and lean top-1 correctness must
not regress.

Deliberate, documented exception to conftest.py's no-real-model
convention: check_regression() only means something against a real
ranking over real embeddings, so this test loads (and, if not already
cached, downloads) the field's actual embedding model. Slower and
network-dependent by design; every other test in this suite stays
hermetic and fake-vector-only on purpose.
"""
from __future__ import annotations

import shutil

import pytest

from eval.agent_trial_token_costs import CORPUS_DIR, _build_field, check_regression
from mf import db

pytestmark = pytest.mark.skipif(not CORPUS_DIR.is_dir(), reason="eval corpus not checked out")


def test_default_search_does_not_regress_above_raw_cost():
    field_dir = _build_field()
    try:
        conn = db.open_field(field_dir)
        try:
            ok, message = check_regression(conn)
        finally:
            conn.close()
    finally:
        shutil.rmtree(field_dir, ignore_errors=True)
    assert ok, message
