"""Performance check for the strategy comparison layer.

plan.md's Performance Goals: the largest comparison this feature defines —
the full 9x9 claiming-age grid over a ~35-year horizon (~2,835 year-
computations) — should complete comfortably within a few seconds on a
laptop. This is a coarse smoke check, not a benchmark.
"""

import itertools
import time

from retirement_planner.comparison import DeterministicReturnAssumption, compare_claiming_age_grid
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember

# Generous budget: "a few seconds" per plan.md, with headroom for slow CI runners.
_BUDGET_SECONDS = 5.0


def test_full_claiming_age_grid_over_a_35_year_horizon_completes_within_budget():
    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=32_000),
            HouseholdMember(person_name="spouse", current_age=58, ss_claim_age=67, ss_annual_benefit=24_000),
        ],
    )
    accounts = AccountBalances(traditional=1_500_000, roth=400_000, taxable=200_000)
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.045)
    grid = [
        {"you": you_age, "spouse": spouse_age}
        for you_age, spouse_age in itertools.product(range(62, 71), range(62, 71))
    ]

    start = time.perf_counter()
    result = compare_claiming_age_grid(
        household=household,
        accounts=accounts,
        annual_spending_need=110_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=95,
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy="fill_to_bracket",
        conversion_bracket_ceiling_or_amount=206_000,
        conversion_window=(2028, 2034),
        return_assumption=return_assumption,
        claiming_age_grid=grid,
    )
    elapsed = time.perf_counter() - start

    assert len(result.projections) == 81
    assert elapsed < _BUDGET_SECONDS, f"81-cell claiming-age grid took {elapsed:.3f}s, expected < {_BUDGET_SECONDS}s"
