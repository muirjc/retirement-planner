"""South Carolina state income tax (FR-006) — a graduated-bracket state.

Genuine bracket-by-bracket math (not a blended-rate approximation) plus an
age-65-and-over retirement-income exclusion. South Carolina does not tax
Social Security benefits, so only `ordinary_income` enters SC's taxable-
income base.

Bracket rates/thresholds and the exclusion amount are illustrative
placeholders (round numbers, right order of magnitude — the source
requirement document cites "SC $15k/person" for the exclusion, which this
module uses directly), not asserted as the actual current SC Code figures —
see quickstart.md and plan.md's Development Workflow gate. `verified=False`
reflects that honestly.

The bracket table documents two tax years (2026, 2027) specifically to
exercise the schedule mechanic FR-012 requires (see User Story 3) — the
2027 rate is a placeholder illustrating a scheduled change, not a real,
currently-legislated SC rate change.
"""

from __future__ import annotations

from datetime import date

from ..bracket_math import apply_progressive_brackets
from ..models import BracketRow, FilingStatus, IncomeComponents, SourcedFigure, StateTaxResult

_AGE_EXCLUSION_THRESHOLD = 65

_BRACKET_TABLE = SourcedFigure(
    name="sc_bracket_table",
    schedule={
        2026: (
            BracketRow(rate=0.00, income_up_to=3_200.0),
            BracketRow(rate=0.03, income_up_to=16_040.0),
            BracketRow(rate=0.064, income_up_to=None),
        ),
        2027: (
            BracketRow(rate=0.00, income_up_to=3_200.0),
            BracketRow(rate=0.03, income_up_to=16_040.0),
            BracketRow(rate=0.06, income_up_to=None),
        ),
    },
    citation="SC Code Ann. §12-6-510 (placeholder — pending verification; 2027 top rate is illustrative)",
    last_verified=date(2026, 8, 27),
    verified=False,
)

_AGE_65_EXCLUSION = SourcedFigure(
    name="sc_age_65_exclusion",
    schedule={2026: 15_000.0, 2027: 15_000.0},
    citation="SC Code Ann. §12-6-1170 (placeholder — pending verification)",
    last_verified=date(2026, 8, 27),
    verified=False,
)


def compute_tax(
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> StateTaxResult:
    """South Carolina's compute_tax() — see
    specs/002-tax-calculation-engine/contracts/tax-api.md for the shape
    every state module conforms to (FR-005)."""
    brackets = _BRACKET_TABLE.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    exclusion_per_filer = _AGE_65_EXCLUSION.value_for_year(tax_year)
    figures_used = [
        _BRACKET_TABLE.usage_for_year(tax_year),
        _AGE_65_EXCLUSION.usage_for_year(tax_year),
    ]

    total_exclusion = sum(exclusion_per_filer for age in filer_ages if age >= _AGE_EXCLUSION_THRESHOLD)
    taxable_income = max(0.0, income.ordinary_income - total_exclusion)

    return StateTaxResult(
        state="SC",
        state_tax_owed=apply_progressive_brackets(taxable_income, brackets),
        figures_used=figures_used,
    )
