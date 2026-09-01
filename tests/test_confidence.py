import pytest

from mf.confidence import DENSE_FLOOR, FLOOR, confidence, normalized_score


def test_normalized_score_divides_by_term_count():
    assert normalized_score(6.0, 3) == 2.0
    assert normalized_score(6.0, 1) == 6.0


def test_normalized_score_rejects_non_positive_term_count():
    with pytest.raises(ValueError):
        normalized_score(6.0, 0)
    with pytest.raises(ValueError):
        normalized_score(6.0, -1)


def test_nothing_passes_is_none():
    # no FTS hit, dense far away, no agreement
    assert confidence(None, 3, fts_dense_agree=False, dense_distance=0.6) == "none"
    # FTS below floor, dense far, no agreement
    assert confidence(4.0, 3, fts_dense_agree=False, dense_distance=0.6) == "none"
    # no dense result at all, FTS below floor
    assert confidence(4.0, 3, fts_dense_agree=False, dense_distance=None) == "none"


def test_zero_term_count_never_counts_as_an_fts_pass():
    assert confidence(6.0, 0, fts_dense_agree=False, dense_distance=0.6) == "none"


def test_fts_floor_alone_is_low():
    # normalized = 9.0 / 3 = 3.0 >= FLOOR, but dense far and no agreement:
    # an exact lexical anchor dense missed. Cited, but only as a lead.
    assert confidence(9.0, 3, fts_dense_agree=False, dense_distance=0.6) == "low"


def test_dense_floor_alone_is_low():
    assert confidence(None, 0, fts_dense_agree=False, dense_distance=0.2) == "low"


def test_agreement_alone_rescues_to_low():
    # both floors fail but FTS and dense picked the same page (the
    # small-field case: bm25 is tiny on a 10-page corpus).
    assert confidence(1.0, 3, fts_dense_agree=True, dense_distance=0.5) == "low"


def test_high_needs_agreement_and_dense_floor():
    assert confidence(9.0, 3, fts_dense_agree=True, dense_distance=0.2) == "high"
    # agreement without the dense floor: the GDPR-shaped case, a
    # topically-adjacent page both retrievers land on. Low, not high.
    assert confidence(9.0, 3, fts_dense_agree=True, dense_distance=0.5) == "low"
    # dense floor without agreement
    assert confidence(9.0, 3, fts_dense_agree=False, dense_distance=0.2) == "low"


def test_exactly_at_floors_counts_as_passing():
    assert confidence(6.0, 3, fts_dense_agree=True, dense_distance=DENSE_FLOOR) == "high"
    assert confidence(6.0, 3, fts_dense_agree=False, dense_distance=0.6) == "low"


def test_floor_overrides():
    assert confidence(6.0, 3, fts_dense_agree=False, dense_distance=0.6, floor=2.5) == "none"
    assert confidence(None, 0, fts_dense_agree=False, dense_distance=0.2, dense_floor=0.1) == "none"


def test_default_floors_match_module_constants():
    assert FLOOR == 2.0
    assert DENSE_FLOOR == 0.30
