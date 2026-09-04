"""eval/mf_harness.py reads pages through mf.page (since 2026-09-03). This
holds the harness's Page view to the shipped parser on the real corpus,
so a parser change that moves a baseline number is visible here first."""
from pathlib import Path

import pytest

from eval import mf_harness
from mf.page import load_page

CORPUS = Path(__file__).resolve().parent.parent / "eval" / "corpus"
pytestmark = pytest.mark.skipif(not CORPUS.is_dir(), reason="eval corpus not checked out")


def test_harness_pages_match_mf_page_on_the_corpus():
    paths = sorted(CORPUS.rglob("*.md"))
    assert len(paths) >= 150
    for path in paths:
        h = mf_harness.load_page(path)
        m = load_page(path)
        assert (h.uuid, h.title, h.summary, h.status, h.tags, h.body, h.body_l1, h.source) == (
            m.uuid, m.title, m.summary, m.status, m.tags, m.body, m.l1, m.source
        ), path.name
