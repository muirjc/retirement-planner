"""Roth conversion execution (FR-008–FR-013, FR-015).

Two strategies ship: filling ordinary income up to a bracket ceiling
(consulting retirement_planner.tax's Social Security taxability logic,
FR-015) and converting a fixed dollar amount each year. Both share an
identical call signature so CONVERSION_STRATEGIES can dispatch on strategy
name alone (mirroring 002's STATE_MODULES registry pattern) — see
specs/003-retirement-account-mechanics/research.md §5.

Implementation note: compute_roth_conversion(), fill_to_bracket_ceiling(),
and fixed_dollar_amount() take an explicit `roth_balance` argument in
addition to `traditional_balance`, which the original
contracts/mechanics-api.md draft omitted. ConversionResult's documented
`ending_roth_balance` field (data-model.md) cannot be computed without
knowing the starting Roth balance, so this parameter was added during
implementation to make that documented field actually computable;
contracts/mechanics-api.md has been updated to match.

See specs/003-retirement-account-mechanics/contracts/mechanics-api.md
("Operations (roth_conversion)" section) for the locked public shape.
"""

from __future__ import annotations

from typing import Callable

from retirement_planner.tax import FilingStatus, IncomeComponents, compute_taxable_social_security

from .models import ConversionResult

RothConversionFunction = Callable[
    [float, float, FilingStatus, int, float, float, float],
    ConversionResult,
]
"""(ordinary_income_established, social_security_gross_benefit,
filing_status, tax_year, traditional_balance, roth_balance,
bracket_ceiling_or_amount) -> ConversionResult
"""


def fill_to_bracket_ceiling(
    ordinary_income_established: float,
    social_security_gross_benefit: float,
    filing_status: FilingStatus,
    tax_year: int,
    traditional_balance: float,
    roth_balance: float,
    ceiling: float,
) -> ConversionResult:
    """Calls retirement_planner.tax.compute_taxable_social_security()
    (FR-015) to determine taxable Social Security given
    ordinary_income_established, then converts
    min(traditional_balance, max(0, ceiling - (ordinary_income_established +
    taxable_social_security))) (FR-009, Acceptance Scenario US3.5).
    figures_used carries the Social Security figures consulted.
    """
    income = IncomeComponents(
        ordinary_income=ordinary_income_established,
        social_security_gross_benefit=social_security_gross_benefit,
    )
    taxable_social_security, figures_used = compute_taxable_social_security(income, filing_status, tax_year)

    established_taxable_income = ordinary_income_established + taxable_social_security
    headroom = max(0.0, ceiling - established_taxable_income)
    amount_converted = min(traditional_balance, headroom)

    return ConversionResult(
        amount_converted=amount_converted,
        ordinary_income_added=amount_converted,
        ending_traditional_balance=traditional_balance - amount_converted,
        ending_roth_balance=roth_balance + amount_converted,
        figures_used=figures_used,
    )


def fixed_dollar_amount(
    ordinary_income_established: float,
    social_security_gross_benefit: float,
    filing_status: FilingStatus,
    tax_year: int,
    traditional_balance: float,
    roth_balance: float,
    fixed_amount: float,
) -> ConversionResult:
    """Converts min(traditional_balance, fixed_amount) (FR-010). Ignores
    ordinary_income_established, social_security_gross_benefit,
    filing_status, and tax_year — accepted only so every registered
    strategy shares an identical call signature. figures_used is always
    empty.
    """
    amount_converted = min(traditional_balance, fixed_amount)
    return ConversionResult(
        amount_converted=amount_converted,
        ordinary_income_added=amount_converted,
        ending_traditional_balance=traditional_balance - amount_converted,
        ending_roth_balance=roth_balance + amount_converted,
        figures_used=[],
    )


CONVERSION_STRATEGIES: dict[str, RothConversionFunction] = {
    "fill_to_bracket": fill_to_bracket_ceiling,
    "fixed_amount": fixed_dollar_amount,
}
"""Registry mapping a strategy name to that strategy's compute function
(FR-014). Adding a new strategy means adding one function + one registry
entry here — nothing else in this package changes (SC-006).
"""


def compute_roth_conversion(
    plan_year: int,
    window: tuple[int, int] | None,
    strategy: str | None,
    bracket_ceiling_or_amount: float | None,
    ordinary_income_established: float,
    social_security_gross_benefit: float,
    filing_status: FilingStatus,
    tax_year: int,
    traditional_balance: float,
    roth_balance: float,
) -> ConversionResult:
    """Returns a zeroed ConversionResult (amount_converted=0,
    figures_used=[]) without calling any strategy if window or strategy is
    None, or if plan_year is outside [window[0], window[1]] inclusive
    (FR-008). Otherwise looks up CONVERSION_STRATEGIES[strategy] and calls
    it with roth_balance and bracket_ceiling_or_amount as the final
    positional arguments. Raises KeyError if strategy has no registered
    function.
    """
    if window is None or strategy is None or not (window[0] <= plan_year <= window[1]):
        return ConversionResult(
            amount_converted=0.0,
            ordinary_income_added=0.0,
            ending_traditional_balance=traditional_balance,
            ending_roth_balance=roth_balance,
            figures_used=[],
        )

    compute = CONVERSION_STRATEGIES[strategy]  # raises KeyError
    return compute(
        ordinary_income_established,
        social_security_gross_benefit,
        filing_status,
        tax_year,
        traditional_balance,
        roth_balance,
        bracket_ceiling_or_amount,
    )
