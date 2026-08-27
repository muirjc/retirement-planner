"""Shared progressive bracket math.

Used by federal.py and every graduated-bracket state module (FR-001, FR-006)
so "genuine bracket-by-bracket math" is one reviewed implementation, not
something each caller reimplements slightly differently.

Not part of the locked contract in specs/002-tax-calculation-engine/
contracts/tax-api.md — this is an internal implementation detail behind
compute_federal_tax() and each state module's compute_tax(), which are the
contract's actual surface.
"""

from __future__ import annotations

from .models import BracketTable


def apply_progressive_brackets(taxable_income: float, brackets: BracketTable) -> float:
    """Genuine progressive bracket math: each dollar is taxed at the rate of
    the bracket it falls in, not the top marginal rate applied to the whole
    amount.
    """
    if taxable_income <= 0:
        return 0.0

    tax = 0.0
    lower_edge = 0.0
    for row in brackets:
        upper_edge = row.income_up_to if row.income_up_to is not None else float("inf")
        if taxable_income <= lower_edge:
            break
        income_in_bracket = min(taxable_income, upper_edge) - lower_edge
        if income_in_bracket > 0:
            tax += income_in_bracket * row.rate
        lower_edge = upper_edge
    return tax
