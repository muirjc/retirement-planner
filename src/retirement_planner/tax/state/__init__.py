"""State tax module registry and dispatcher (FR-005, SC-006).

Every state module exposes one function, `compute_tax(income, filer_ages,
filing_status, tax_year) -> StateTaxResult`, with an identical signature —
STATE_MODULES maps a state code to that function. compute_state_tax() never
branches on which state it's calling; it only looks the function up and
calls it. Adding a new state means adding one module + one registry entry
here — nothing else in this package changes.

See specs/002-tax-calculation-engine/contracts/tax-api.md ("Operations"
section, "retirement_planner.tax.state") for the locked public shape of
STATE_MODULES and compute_state_tax(), and for what every registered
state module's compute_tax() function must look like.
"""

from __future__ import annotations

from typing import Callable

from ..models import FilingStatus, IncomeComponents, StateTaxResult
from . import de, fl, nc, sc

StateTaxFunction = Callable[[IncomeComponents, list[int], FilingStatus, int], StateTaxResult]

STATE_MODULES: dict[str, StateTaxFunction] = {
    "SC": sc.compute_tax,
    "DE": de.compute_tax,
    "FL": fl.compute_tax,
    "NC": nc.compute_tax,
}


def compute_state_tax(
    state: str,
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> StateTaxResult:
    """Looks up STATE_MODULES[state] and calls it. Raises KeyError if
    `state` has no registered module. Raises UnsupportedTaxYearError if a
    figure the state's module needs has no entry for tax_year.
    """
    compute = STATE_MODULES[state]
    return compute(income, filer_ages, filing_status, tax_year)


__all__ = ["STATE_MODULES", "StateTaxFunction", "compute_state_tax"]
