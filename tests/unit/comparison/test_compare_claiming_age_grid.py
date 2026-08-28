"""Unit tests for compare_claiming_age_grid() (US4)."""

import itertools

import pytest

from retirement_planner.comparison import (
    DeterministicReturnAssumption,
    compare_claiming_age_grid,
    run_plan_projection,
)
from retirement_planner.comparison.models import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember

_HOUSEHOLD = Household(
    filing_status="married_filing_jointly",
    members=[
        HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=32_000),
        HouseholdMember(person_name="spouse", current_age=58, ss_claim_age=67, ss_annual_benefit=24_000),
    ],
)
_ACCOUNTS = AccountBalances(traditional=1_500_000, roth=400_000, taxable=200_000)
_RETURN_ASSUMPTION = DeterministicReturnAssumption(annual_real_return=0.045)


def _run(grid):
    return compare_claiming_age_grid(
        household=_HOUSEHOLD,
        accounts=_ACCOUNTS,
        annual_spending_need=110_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=75,
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        return_assumption=_RETURN_ASSUMPTION,
        claiming_age_grid=grid,
    )


def test_every_grid_entry_shares_the_identical_shared_inputs():
    grid = [{"you": 62, "spouse": 62}, {"you": 70, "spouse": 70}]
    result = _run(grid)
    assert result.dimension == "claiming_age_grid"
    assert len(result.projections) == 2
    assert all(p.return_assumption == _RETURN_ASSUMPTION for p in result.projections)
    assert all(p.strategy.withdrawal_strategy == "rmd_taxable_traditional_roth" for p in result.projections)
    assert all(p.strategy.conversion_strategy is None for p in result.projections)


def test_earlier_and_later_claiming_produce_different_outcomes():
    grid = [{"you": 62, "spouse": 62}, {"you": 70, "spouse": 70}]
    result = _run(grid)
    early = next(p for p in result.projections if p.strategy.claiming_ages == {"you": 62, "spouse": 62})
    late = next(p for p in result.projections if p.strategy.claiming_ages == {"you": 70, "spouse": 70})
    assert early.outcome.cumulative_tax_paid != late.outcome.cumulative_tax_paid


def test_grid_entry_matching_original_claiming_ages_reproduces_standalone_projection():
    original_claiming_ages = {"you": 67, "spouse": 67}
    grid = [{"you": 62, "spouse": 62}, dict(original_claiming_ages)]

    comparison = _run(grid)
    matching = next(p for p in comparison.projections if p.strategy.claiming_ages == original_claiming_ages)

    standalone_strategy = StrategyConfiguration(
        label="standalone",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages=original_claiming_ages,
    )
    standalone = run_plan_projection(
        household=_HOUSEHOLD,
        accounts=_ACCOUNTS,
        annual_spending_need=110_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=75,
        strategy=standalone_strategy,
        return_assumption=_RETURN_ASSUMPTION,
    )

    assert matching.outcome == standalone.outcome


def test_claiming_age_outside_bounds_raises_value_error():
    with pytest.raises(ValueError):
        _run([{"you": 61, "spouse": 67}])
    with pytest.raises(ValueError):
        _run([{"you": 67, "spouse": 71}])


def test_full_grid_covers_every_combination():
    grid = [
        {"you": you_age, "spouse": spouse_age}
        for you_age, spouse_age in itertools.product(range(62, 71), range(62, 71))
    ]
    result = _run(grid)
    assert len(result.projections) == 9 * 9


def test_single_entry_grid_still_returns_a_valid_comparison_result():
    result = _run([{"you": 67, "spouse": 67}])
    assert len(result.projections) == 1
