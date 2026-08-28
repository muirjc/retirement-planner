"""Performance check for retirement account mechanics.

plan.md's Performance Goals: a single plan year's RMD + withdrawal + Roth
conversion computation should complete in well under 10ms. This is a coarse
smoke check, not a benchmark — it exists to catch an accidental regression
(e.g., a rule table being rebuilt on every call instead of loaded once at
import time), not to micro-optimize.
"""

import time

from retirement_planner.mechanics import AccountBalances, compute_plan_year_mechanics, compute_rmd

# Generous budget: "well under 10ms" per plan.md, with headroom for slow CI runners.
_BUDGET_SECONDS = 0.01


def test_single_plan_year_mechanics_completes_well_under_ten_ms():
    start = time.perf_counter()

    rmd = compute_rmd(traditional_balance=900_000, member_age=75, tax_year=2026)
    compute_plan_year_mechanics(
        plan_year=2030,
        tax_year=2026,
        spending_need=110_000,
        starting_balances=AccountBalances(traditional=900_000, roth=200_000, taxable=50_000),
        rmd_amount=rmd.required_amount,
        social_security_gross_benefit=32_000,
        filing_status="married_filing_jointly",
        conversion_window=(2028, 2034),
        conversion_strategy="fill_to_bracket",
        conversion_bracket_ceiling_or_amount=206_000,
        rmd_figures_used=rmd.figures_used,
    )

    elapsed = time.perf_counter() - start

    assert elapsed < _BUDGET_SECONDS, f"one plan year's mechanics took {elapsed:.5f}s, expected < {_BUDGET_SECONDS}s"
