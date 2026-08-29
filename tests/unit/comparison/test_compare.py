"""Unit tests for inherited_accounts threading through comparison/compare.py
(012-inherited-ira-rmd, US1) -- the "fresh copy per candidate" property
comparison-api.md requires, since run_plan_projection() mutates each
InheritedAccountBalance's balance in place year-by-year.
"""

from retirement_planner.comparison import (
    DeterministicReturnAssumption,
    StrategyConfiguration,
    compare_roth_conversion_strategies,
)
from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
from retirement_planner.scenario import Household, HouseholdMember

_HOUSEHOLD = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
)
_ACCOUNTS = AccountBalances(traditional=0, roth=0, taxable=1_000_000)
_SHARES = {"you": 0.0}
_RETURN_ASSUMPTION = DeterministicReturnAssumption(annual_real_return=0.0)


def _candidates():
    return [
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


def test_callers_own_inherited_account_balance_is_never_mutated():
    inherited_accounts = [
        InheritedAccountBalance(
            account_id="traditional-1",
            balance=250_000.0,
            death_year=2023,
            decedent_age_at_death=80,
            depletion_deadline_year=2033,
        )
    ]

    compare_roth_conversion_strategies(
        household=_HOUSEHOLD,
        accounts=_ACCOUNTS,
        traditional_ownership_shares=_SHARES,
        inherited_accounts=inherited_accounts,
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        withdrawal_strategy="rmd_taxable_traditional_roth",
        claiming_ages={"you": 67},
        return_assumption=_RETURN_ASSUMPTION,
        candidates=_candidates(),
    )

    # run_plan_projection() ran twice (once per candidate) and mutates
    # balance in place -- the caller's own original instance must still
    # read its untouched starting balance.
    assert inherited_accounts[0].balance == 250_000.0


def test_no_cross_candidate_leakage_in_inherited_distributions():
    inherited_accounts = [
        InheritedAccountBalance(
            account_id="traditional-1",
            balance=250_000.0,
            death_year=2023,
            decedent_age_at_death=80,
            depletion_deadline_year=2033,
        )
    ]

    result = compare_roth_conversion_strategies(
        household=_HOUSEHOLD,
        accounts=_ACCOUNTS,
        traditional_ownership_shares=_SHARES,
        inherited_accounts=inherited_accounts,
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        withdrawal_strategy="rmd_taxable_traditional_roth",
        claiming_ages={"you": 67},
        return_assumption=_RETURN_ASSUMPTION,
        candidates=_candidates(),
    )

    # Both candidates started from the identical, unmutated inherited
    # balance -- their first-year inherited distributions must therefore
    # be identical to each other (neither candidate's projection saw the
    # other's already-decremented balance).
    first_years = [projection.years[0] for projection in result.projections]
    distributions = {year.mechanics.withdrawal_plan.inherited_distribution_drawn for year in first_years}
    assert len(distributions) == 1
    assert distributions.pop() > 0
