"""Unit tests for run_simulation()'s survival-adjusted success scoring
(US5): additive metric, non-interference with the fixed-horizon rate,
threshold-based determination, and the missing-curve rejection (FR-017,
FR-018).
"""

from datetime import date

import pytest

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.simulation.models import ReturnPath, SurvivalCurve

_HOUSEHOLD = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=90, ss_claim_age=99, ss_annual_benefit=0)],
)
_ACCOUNTS = AccountBalances(traditional=0, roth=0, taxable=100)
_STRATEGY = StrategyConfiguration(
    label="test",
    withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None,
    conversion_bracket_ceiling_or_amount=None,
    conversion_window=None,
    claiming_ages={"you": 99},
)
_COMMON_KWARGS = dict(
    household=_HOUSEHOLD,
    accounts=_ACCOUNTS,
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=50,
    state="FL",
    reference_tax_year=2026,
    start_plan_year=1,
    start_tax_year=2026,
    plan_to_age=91,  # 2-year horizon: ages 90 and 91
    strategy=_STRATEGY,
)
# Same controlled shortfall design as test_monte_carlo.py: year1 return 0.0
# leaves year2 fully funded (no shortfall); year1 return -0.5 leaves year2
# short by 25.
_PATH_OK = ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0], generation_mode="parametric", figures_used=[])
_PATH_FAIL = ReturnPath(start_plan_year=1, annual_returns=[-0.5, 0.0], generation_mode="parametric", figures_used=[])


def _curve(probability_at_91: float) -> SurvivalCurve:
    return SurvivalCurve(
        person_name="you",
        probabilities_by_age={90: 1.0, 91: probability_at_91},
        citation="test fixture",
        last_verified=date(2026, 8, 28),
        verified=False,
    )


def test_survival_adjusted_success_rate_is_additive_and_does_not_affect_fixed_horizon_rate():
    from retirement_planner.simulation.monte_carlo import run_simulation

    without_survival = run_simulation(
        **_COMMON_KWARGS, return_paths=[_PATH_OK, _PATH_FAIL], candidate_label="test"
    )
    with_survival = run_simulation(
        **_COMMON_KWARGS, return_paths=[_PATH_OK, _PATH_FAIL], candidate_label="test",
        survival_curves={"you": _curve(probability_at_91=0.9)},  # presumed alive at shortfall year
    )

    assert without_survival.survival_adjusted_success_rate is None
    assert with_survival.survival_adjusted_success_rate is not None
    assert with_survival.success_rate == without_survival.success_rate == pytest.approx(0.5)


def test_shortfall_after_presumed_death_counts_as_survival_adjusted_success():
    from retirement_planner.simulation.monte_carlo import run_simulation

    # The shortfall occurs at plan_year 2 (age 91). A survival curve
    # placing "you" as more likely deceased than alive at 91 (probability
    # < 0.5) means the fixed-horizon failure at that path counts as a
    # survival-adjusted success instead.
    run = run_simulation(
        **_COMMON_KWARGS, return_paths=[_PATH_OK, _PATH_FAIL], candidate_label="test",
        survival_curves={"you": _curve(probability_at_91=0.2)},
    )

    assert run.success_rate == pytest.approx(0.5)  # unaffected: _PATH_FAIL still a fixed-horizon failure
    assert run.survival_adjusted_success_rate == pytest.approx(1.0)  # both paths count as survival-adjusted success


def test_run_simulation_raises_key_error_for_missing_survival_curve():
    from retirement_planner.simulation.monte_carlo import run_simulation

    with pytest.raises(KeyError):
        run_simulation(
            **_COMMON_KWARGS, return_paths=[_PATH_OK], candidate_label="test",
            survival_curves={},  # missing "you"
        )


# -- 023-probabilistic-death-draws (rp-vgv): death_year_draws validation ----


def test_death_year_draws_requires_survival_curves_to_also_be_given():
    from retirement_planner.simulation.monte_carlo import run_simulation

    with pytest.raises(ValueError):
        run_simulation(
            **_COMMON_KWARGS, return_paths=[_PATH_OK], candidate_label="test",
            death_year_draws=[{"you": None}],  # survival_curves omitted entirely
        )


def test_death_year_draws_length_must_match_return_paths():
    from retirement_planner.simulation.monte_carlo import run_simulation

    with pytest.raises(ValueError):
        run_simulation(
            **_COMMON_KWARGS, return_paths=[_PATH_OK, _PATH_FAIL], candidate_label="test",
            survival_curves={"you": _curve(probability_at_91=0.9)},
            death_year_draws=[{"you": None}],  # one entry, but two return_paths
        )


def test_death_year_draws_coexists_with_survival_adjusted_success_rate():
    """spec.md Edge Cases / FR-008: both may be requested at once --
    survival_adjusted_success_rate's own formula is computed unchanged,
    over whatever path_results this call produced."""
    from retirement_planner.simulation.monte_carlo import run_simulation

    run = run_simulation(
        **_COMMON_KWARGS, return_paths=[_PATH_OK, _PATH_FAIL], candidate_label="test",
        survival_curves={"you": _curve(probability_at_91=0.9)},
        death_year_draws=[{"you": None}, {"you": None}],  # no-op draws -- isolates the coexistence check
    )

    assert run.survival_adjusted_success_rate is not None
    assert run.success_rate == pytest.approx(0.5)
