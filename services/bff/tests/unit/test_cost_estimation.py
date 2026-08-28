"""Unit tests for rp_bff.cost_estimation (research.md §5, FR-018): a
conservative estimate of a run/comparison request's cost, and rejection
once that estimate exceeds the 30-second threshold.

PER_UNIT_COST_SECONDS = 0.0001 (0.1ms/path-year-candidate) was verified
against 006's actual measured reference-scale benchmark (3.77s for a
5,000-path/36-year run plus a 5,000-path/3-state/1-year comparison,
combined) before being adopted -- see research.md §5 for how an earlier,
36x-too-conservative draft value would have caused this feature's own cost
gate to incorrectly reject the reference-scale request SC-003 requires to
succeed.
"""

import pytest


def test_estimate_cost_seconds_scales_with_paths_candidates_and_horizon():
    from rp_bff.cost_estimation import PER_UNIT_COST_SECONDS, estimate_cost_seconds

    assert estimate_cost_seconds(path_count=5_000, candidate_count=1, horizon_years=36) == pytest.approx(
        5_000 * 1 * 36 * PER_UNIT_COST_SECONDS
    )
    assert estimate_cost_seconds(path_count=5_000, candidate_count=9, horizon_years=36) == pytest.approx(
        5_000 * 9 * 36 * PER_UNIT_COST_SECONDS
    )


def test_check_cost_within_budget_passes_just_under_threshold():
    from rp_bff.cost_estimation import check_cost_within_budget

    # 8,000 paths x 1 candidate x 36 years x 0.0001s/unit = 28.8s < 30s.
    check_cost_within_budget(path_count=8_000, candidate_count=1, horizon_years=36)


def test_check_cost_within_budget_rejects_just_over_threshold():
    from rp_bff.cost_estimation import CostBudgetExceededError, REJECTION_THRESHOLD_SECONDS, check_cost_within_budget

    # 9,000 paths x 1 candidate x 36 years x 0.0001s/unit = 32.4s > 30s.
    with pytest.raises(CostBudgetExceededError) as exc_info:
        check_cost_within_budget(path_count=9_000, candidate_count=1, horizon_years=36)

    assert exc_info.value.estimated_seconds > REJECTION_THRESHOLD_SECONDS
    assert exc_info.value.budget_seconds == REJECTION_THRESHOLD_SECONDS


def test_reference_scale_single_run_stays_within_budget():
    """The exact reference-scale single run (5,000 paths, 36-year horizon,
    one candidate) that US3.1/SC-003 require to succeed MUST NOT be
    rejected by this feature's own cost gate (research.md §5)."""
    from rp_bff.cost_estimation import check_cost_within_budget

    check_cost_within_budget(path_count=5_000, candidate_count=1, horizon_years=36)


def test_a_genuinely_oversized_comparison_is_still_rejected():
    """A 9-state comparison at the full 36-year reference-scale horizon
    (5,000 paths x 9 states x 36 years) is a real, currently-too-large
    request -- confirms the gate still does its job for genuinely
    oversized requests, not just anything at reference scale (FR-018)."""
    from rp_bff.cost_estimation import CostBudgetExceededError, check_cost_within_budget

    with pytest.raises(CostBudgetExceededError):
        check_cost_within_budget(path_count=5_000, candidate_count=9, horizon_years=36)
