"""Florida state income tax (FR-007) — a zero-income-tax state.

Florida has no state income tax, so this module always returns zero and
consults no figures at all — it needs no bracket table, no exclusion, and
no citation, and it never raises UnsupportedTaxYearError, since it has no
schedule to be out of range for.
"""

from __future__ import annotations

from ..models import FilingStatus, IncomeComponents, StateTaxResult


def compute_tax(
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> StateTaxResult:
    """Florida's compute_tax() — see
    specs/002-tax-calculation-engine/contracts/tax-api.md for the shape
    every state module conforms to (FR-005)."""
    return StateTaxResult(state="FL", state_tax_owed=0.0, figures_used=[])
