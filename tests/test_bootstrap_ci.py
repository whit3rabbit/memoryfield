"""Part B of the token-savings/recall test plan: `bootstrap_ci` and
`BaselineMetrics` had no direct coverage before this (confirmed by grep
of tests/test_eval_harness.py, the only existing test to touch
eval/mf_harness.py or eval/run_baselines.py at all). R@5 and MRR now get
the same 95% CI treatment P@3/P@5 already had, so `bootstrap_ci` needs to
handle fractional per-query values (R@5's `hits / len(answer_uuids)`,
MRR's `1 / rank`), not just the 0/1 hits it was written for.
"""
from pathlib import Path

from eval.mf_harness import BaselineMetrics, bootstrap_ci


def test_bootstrap_ci_empty_returns_zeros():
    assert bootstrap_ci([]) == (0.0, 0.0, 0.0)


def test_bootstrap_ci_constant_values_has_zero_width_interval():
    point, lo, hi = bootstrap_ci([1, 1, 1, 1], n_resamples=200)
    assert point == 1.0
    assert lo == hi == 1.0


def test_bootstrap_ci_fractional_values_point_is_the_mean():
    values = [0.5, 1.0, 0.0, 0.5]
    point, lo, hi = bootstrap_ci(values, n_resamples=500)
    assert point == sum(values) / len(values)
    assert lo <= point <= hi


def test_bootstrap_ci_is_deterministic_for_a_fixed_seed():
    values = [0.0, 1.0, 0.5, 0.25, 1.0]
    a = bootstrap_ci(values, n_resamples=300, rng_seed=7)
    b = bootstrap_ci(values, n_resamples=300, rng_seed=7)
    assert a == b


def test_baseline_metrics_as_dict_includes_r_at_5_and_mrr_ci():
    m = BaselineMetrics(
        baseline="hybrid",
        domain="codebase",
        n_queries=10,
        p_at_3=0.9,
        p_at_5=0.95,
        r_at_5=0.8,
        mrr=0.85,
        stub_end_rate=0.7,
        stub_end_given_hit_rate=0.75,
        tokens_stub_median=50.0,
        tokens_stub_p95=90.0,
        tokens_l1_median=200.0,
        tokens_full_median=400.0,
        details_path=Path("eval/results/hybrid_codebase.json"),
        r_at_5_ci=(0.8, 0.6, 0.95),
        mrr_ci=(0.85, 0.7, 0.97),
    )
    d = m.as_dict()
    assert d["r_at_5_ci_low"] == 0.6
    assert d["r_at_5_ci_high"] == 0.95
    assert d["mrr_ci_low"] == 0.7
    assert d["mrr_ci_high"] == 0.97
