"""Unit tests for compare_roth_conversion_strategies() (US2)."""

from retirement_planner.comparison import (
    DeterministicReturnAssumption,
    StrategyConfiguration,
    compare_roth_conversion_strategies,
)
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
_SHARES = {"you": 0.6, "spouse": 0.4}
_RETURN_ASSUMPTION = DeterministicReturnAssumption(annual_real_return=0.045)


def _run(candidates):
    return compare_roth_conversion_strategies(
        household=_HOUSEHOLD,
        accounts=_ACCOUNTS,
        traditional_ownership_shares=_SHARES,
        annual_spending_need=110_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=70,
        withdrawal_strategy="rmd_taxable_traditional_roth",
        claiming_ages={"you": 67, "spouse": 67},
        return_assumption=_RETURN_ASSUMPTION,
        candidates=candidates,
    )


def test_every_candidate_shares_the_identical_return_assumption():
    candidates = [
        StrategyConfiguration(
            label="fill_to_bracket",
            withdrawal_strategy="ignored",
            conversion_strategy="fill_to_bracket",
            conversion_bracket_ceiling_or_amount=206_000,
            conversion_window=(2026, 2030),
            claiming_ages={"ignored": 0},
        ),
        StrategyConfiguration(
            label="no_conversion",
            withdrawal_strategy="ignored",
            conversion_strategy=None,
            conversion_bracket_ceiling_or_amount=None,
            conversion_window=None,
            claiming_ages={"ignored": 0},
        ),
    ]
    result = _run(candidates)
    assert result.dimension == "roth_conversion_strategy"
    assert len(result.projections) == 2
    assert all(p.return_assumption == _RETURN_ASSUMPTION for p in result.projections)


def test_no_conversion_and_fill_to_bracket_produce_different_outcomes():
    candidates = [
        StrategyConfiguration(
            label="fill_to_bracket",
            withdrawal_strategy="x",
            conversion_strategy="fill_to_bracket",
            conversion_bracket_ceiling_or_amount=206_000,
            conversion_window=(2026, 2030),
            claiming_ages={},
        ),
        StrategyConfiguration(
            label="no_conversion",
            withdrawal_strategy="x",
            conversion_strategy=None,
            conversion_bracket_ceiling_or_amount=None,
            conversion_window=None,
            claiming_ages={},
        ),
    ]
    result = _run(candidates)
    fill = next(p for p in result.projections if p.strategy.label == "fill_to_bracket")
    none = next(p for p in result.projections if p.strategy.label == "no_conversion")
    assert fill.outcome.cumulative_tax_paid != none.outcome.cumulative_tax_paid
    assert fill.outcome.ending_balance != none.outcome.ending_balance


def test_two_strategies_with_no_actual_difference_produce_identical_outcomes():
    # Both candidates configured with a conversion window that has already
    # ended before the horizon starts — neither ever converts anything.
    candidates = [
        StrategyConfiguration(
            label="a",
            withdrawal_strategy="x",
            conversion_strategy="fill_to_bracket",
            conversion_bracket_ceiling_or_amount=206_000,
            conversion_window=(2000, 2001),
            claiming_ages={},
        ),
        StrategyConfiguration(
            label="b",
            withdrawal_strategy="x",
            conversion_strategy="fixed_amount",
            conversion_bracket_ceiling_or_amount=50_000,
            conversion_window=(2000, 2001),
            claiming_ages={},
        ),
    ]
    result = _run(candidates)
    a, b = result.projections
    assert a.outcome == b.outcome


def test_shared_withdrawal_strategy_and_claiming_ages_overwrite_every_candidate():
    candidates = [
        StrategyConfiguration(
            label="a",
            withdrawal_strategy="not_a_real_strategy",
            conversion_strategy=None,
            conversion_bracket_ceiling_or_amount=None,
            conversion_window=None,
            claiming_ages={"nonsense": 1},
        )
    ]
    # Would raise KeyError if the candidate's own (bogus) withdrawal_strategy
    # were used instead of this call's shared one.
    result = _run(candidates)
    assert result.projections[0].strategy.withdrawal_strategy == "rmd_taxable_traditional_roth"
    assert result.projections[0].strategy.claiming_ages == {"you": 67, "spouse": 67}


def test_single_candidate_still_returns_a_valid_comparison_result():
    candidates = [
        StrategyConfiguration(
            label="only",
            withdrawal_strategy="x",
            conversion_strategy=None,
            conversion_bracket_ceiling_or_amount=None,
            conversion_window=None,
            claiming_ages={},
        )
    ]
    result = _run(candidates)
    assert len(result.projections) == 1
