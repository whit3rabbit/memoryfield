import pytest

from mf.confidence import FLOOR, confidence, normalized_score


def test_normalized_score_divides_by_term_count():
    assert normalized_score(6.0, 3) == 2.0
    assert normalized_score(6.0, 1) == 6.0


def test_normalized_score_rejects_non_positive_term_count():
    with pytest.raises(ValueError):
        normalized_score(6.0, 0)
    with pytest.raises(ValueError):
        normalized_score(6.0, -1)


def test_no_score_is_none():
    assert confidence(None, 3, fts_dense_agree=True) == "none"


def test_zero_term_count_is_none():
    assert confidence(6.0, 0, fts_dense_agree=True) == "none"


def test_below_floor_is_none_regardless_of_agreement():
    # normalized = 4.0 / 3 = 1.33, below the default floor (2.0)
    assert confidence(4.0, 3, fts_dense_agree=True) == "none"
    assert confidence(4.0, 3, fts_dense_agree=False) == "none"


def test_above_floor_and_agree_is_high():
    # normalized = 9.0 / 3 = 3.0, above the default floor
    assert confidence(9.0, 3, fts_dense_agree=True) == "high"


def test_above_floor_and_disagree_is_low():
    assert confidence(9.0, 3, fts_dense_agree=False) == "low"


def test_exactly_at_floor_counts_as_passing():
    # normalized = 6.0 / 3 = 2.0 == FLOOR
    assert confidence(6.0, 3, fts_dense_agree=True) == "high"


def test_custom_floor_override():
    # normalized = 6.0 / 3 = 2.0; with a stricter floor this now fails
    assert confidence(6.0, 3, fts_dense_agree=True, floor=2.5) == "none"


def test_default_floor_matches_module_constant():
    assert FLOOR == 2.0
