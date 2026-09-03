"""Delaware state income tax (FR-006) — a graduated-bracket state.

Genuine bracket-by-bracket math (not a blended-rate approximation) plus an
age-60-and-over retirement-income exclusion. Delaware does not tax Social
Security benefits, so only `ordinary_income` enters DE's taxable-income
base.

Bracket rates/thresholds and the exclusion amount are illustrative
placeholders (round numbers, right order of magnitude — the source
requirement document cites "DE $12,500/person" for the exclusion, which
this module uses directly), not asserted as the actual current Delaware
Code figures — see quickstart.md and plan.md's Development Workflow gate.
`verified=False` reflects that honestly.

rp-wif: the schedule below originally documented only tax year 2026, so
any projection running a real multi-decade plan horizon (the tool's
actual use case) hit UnsupportedTaxYearError starting tax year 2027 --
fixed by repeating the same 2026 figures across `_DOCUMENTED_YEARS`,
matching every other module's convention (tax/federal.py,
mechanics/rmd.py, ...). The figures themselves, and their
illustrative-not-real status, are unchanged.
"""

from __future__ import annotations

from datetime import date

from ..bracket_math import apply_progressive_brackets_detailed
from ..models import BracketRow, FilingStatus, IncomeComponents, SourcedFigure, StateTaxResult

_AGE_EXCLUSION_THRESHOLD = 60

_DOCUMENTED_YEARS = range(2020, 2075)

_BRACKETS = (
    BracketRow(rate=0.022, income_up_to=5_000.0),
    BracketRow(rate=0.039, income_up_to=10_000.0),
    BracketRow(rate=0.048, income_up_to=20_000.0),
    BracketRow(rate=0.052, income_up_to=25_000.0),
    BracketRow(rate=0.0555, income_up_to=60_000.0),
    BracketRow(rate=0.066, income_up_to=None),
)

_BRACKET_TABLE = SourcedFigure(
    name="de_bracket_table",
    schedule={year: _BRACKETS for year in _DOCUMENTED_YEARS},
    citation="Del. Code Ann. tit. 30 §1102 (placeholder — pending verification)",
    last_verified=date(2026, 8, 27),
    verified=False,
)

_AGE_60_EXCLUSION = SourcedFigure(
    name="de_age_60_exclusion",
    schedule={year: 12_500.0 for year in _DOCUMENTED_YEARS},
    citation="Del. Code Ann. tit. 30 §1106 (placeholder — pending verification)",
    last_verified=date(2026, 8, 27),
    verified=False,
)


def compute_tax(
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> StateTaxResult:
    """Delaware's compute_tax() — see
    specs/002-tax-calculation-engine/contracts/tax-api.md for the shape
    every state module conforms to (FR-005)."""
    brackets = _BRACKET_TABLE.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    exclusion_per_filer = _AGE_60_EXCLUSION.value_for_year(tax_year)
    figures_used = [
        _BRACKET_TABLE.usage_for_year(tax_year),
        _AGE_60_EXCLUSION.usage_for_year(tax_year),
    ]

    total_exclusion = sum(exclusion_per_filer for age in filer_ages if age >= _AGE_EXCLUSION_THRESHOLD)
    taxable_income = max(0.0, income.ordinary_income - total_exclusion)
    state_tax_owed, bracket_breakdown = apply_progressive_brackets_detailed(taxable_income, brackets)

    return StateTaxResult(
        state="DE",
        state_tax_owed=state_tax_owed,
        figures_used=figures_used,
        taxable_income=taxable_income,
        exclusion_applied=total_exclusion,
        bracket_breakdown=bracket_breakdown,
    )
