"""Performance check for the tax calculation engine.

plan.md's Performance Goals: a single federal-or-state tax computation
should complete in well under 10ms. This is a coarse smoke check, not a
benchmark — it exists to catch an accidental regression (e.g., rule tables
being rebuilt on every call instead of loaded once at import time), not to
micro-optimize.
"""

import time

from retirement_planner.tax import IncomeComponents
from retirement_planner.tax.federal import compute_federal_tax
from retirement_planner.tax.state import compute_state_tax

# Generous budget: "well under 10ms" per plan.md, with headroom for slow CI runners.
_BUDGET_SECONDS = 0.01


def test_federal_and_state_computation_completes_well_under_ten_ms():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)

    start = time.perf_counter()
    compute_federal_tax(income, filing_status="married_filing_jointly", tax_year=2026)
    compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    compute_state_tax("DE", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    compute_state_tax("FL", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    elapsed = time.perf_counter() - start

    assert elapsed < _BUDGET_SECONDS, (
        f"federal + 3 state computations took {elapsed:.5f}s, expected < {_BUDGET_SECONDS}s"
    )
