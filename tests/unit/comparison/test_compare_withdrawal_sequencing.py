"""Unit tests for compare_withdrawal_sequencing_strategies() (US3)."""

from retirement_planner.comparison import (
    DeterministicReturnAssumption,
    StrategyConfiguration,
    compare_withdrawal_sequencing_strategies,
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


def _candidate(label, withdrawal_strategy):
    return StrategyConfiguration(
        label=label,
        withdrawal_strategy=withdrawal_strategy,
        conversion_strategy="ignored",
        conversion_bracket_ceiling_or_amount=999,
        conversion_window=(1900, 1901),
        claiming_ages={"ignored": 0},
    )


def _run(candidates):
    return compare_withdrawal_sequencing_strategies(
        household=_HOUSEHOLD,
        accounts=_ACCOUNTS,
        traditional_ownership_shares=_SHARES,
        annual_spending_need=110_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=70,
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67},
        return_assumption=_RETURN_ASSUMPTION,
        candidates=candidates,
    )


def test_every_candidate_shares_the_identical_shared_inputs():
    candidates = [
        _candidate("taxable_first", "rmd_taxable_traditional_roth"),
        _candidate("traditional_first", "rmd_traditional_taxable_roth"),
    ]
    result = _run(candidates)
    assert result.dimension == "withdrawal_sequencing"
    assert len(result.projections) == 2
    assert all(p.return_assumption == _RETURN_ASSUMPTION for p in result.projections)
    assert all(p.strategy.conversion_strategy is None for p in result.projections)
    assert all(p.strategy.claiming_ages == {"you": 67, "spouse": 67} for p in result.projections)


def test_different_orders_produce_different_outcomes():
    candidates = [
        _candidate("taxable_first", "rmd_taxable_traditional_roth"),
        _candidate("traditional_first", "rmd_traditional_taxable_roth"),
    ]
    result = _run(candidates)
    taxable_first = next(p for p in result.projections if p.strategy.label == "taxable_first")
    traditional_first = next(p for p in result.projections if p.strategy.label == "traditional_first")
    assert (
        taxable_first.outcome.cumulative_tax_paid != traditional_first.outcome.cumulative_tax_paid
        or taxable_first.outcome.ending_balance != traditional_first.outcome.ending_balance
    )


def test_orders_converge_once_both_have_exhausted_the_same_account_types():
    # Both taxable and traditional are small enough to be fully exhausted
    # in year one regardless of draw order — whichever order drains them,
    # the same total leaves both accounts at exactly $0, so the two orders
    # converge to an identical result from that point on.
    small_accounts = AccountBalances(traditional=2_000, roth=400_000, taxable=1_000)
    candidates = [
        _candidate("taxable_first", "rmd_taxable_traditional_roth"),
        _candidate("traditional_first", "rmd_traditional_taxable_roth"),
    ]
    result = compare_withdrawal_sequencing_strategies(
        household=_HOUSEHOLD,
        accounts=small_accounts,
        traditional_ownership_shares=_SHARES,
        annual_spending_need=110_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=70,
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67},
        return_assumption=_RETURN_ASSUMPTION,
        candidates=candidates,
    )
    taxable_first = next(p for p in result.projections if p.strategy.label == "taxable_first")
    traditional_first = next(p for p in result.projections if p.strategy.label == "traditional_first")
    last_year_taxable_first = taxable_first.years[-1]
    last_year_traditional_first = traditional_first.years[-1]
    assert last_year_taxable_first.ending_balances == last_year_traditional_first.ending_balances


def test_single_candidate_still_returns_a_valid_comparison_result():
    result = _run([_candidate("only", "rmd_taxable_traditional_roth")])
    assert len(result.projections) == 1
