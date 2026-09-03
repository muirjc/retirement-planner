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
currently-legislated SC rate change. rp-wif: that two-year table was
never extended past 2027, so any projection running a real multi-decade
plan horizon (the tool's actual use case) hit UnsupportedTaxYearError
starting tax year 2028 -- fixed by repeating each of the two tables
across its own sub-range of `_DOCUMENTED_YEARS`, mirroring how
mechanics/rmd.py already encodes SECURE 2.0's own 73->75 RMD-age step as
two merged sub-ranges of one schedule dict. The 2026/2027 tables
themselves, and their illustrative-not-real status, are unchanged.
"""

from __future__ import annotations

from datetime import date

from ..bracket_math import apply_progressive_brackets_detailed
from ..models import BracketRow, FilingStatus, IncomeComponents, SourcedFigure, StateTaxResult

_AGE_EXCLUSION_THRESHOLD = 65

# rp-wif: matches every other module's _DOCUMENTED_YEARS convention
# (tax/federal.py, mechanics/rmd.py, ...) -- covers any realistic plan
# horizon so a multi-year projection never hits UnsupportedTaxYearError.
_DOCUMENTED_YEARS = range(2020, 2075)

_2026_BRACKETS = (
    BracketRow(rate=0.00, income_up_to=3_200.0),
    BracketRow(rate=0.03, income_up_to=16_040.0),
    BracketRow(rate=0.064, income_up_to=None),
)
_2027_BRACKETS = (
    BracketRow(rate=0.00, income_up_to=3_200.0),
    BracketRow(rate=0.03, income_up_to=16_040.0),
    BracketRow(rate=0.06, income_up_to=None),
)

_BRACKET_TABLE = SourcedFigure(
    name="sc_bracket_table",
    schedule={
        # Before 2027: the originally-documented 2026 table. From 2027
        # on: the originally-documented 2027 table (its illustrative
        # scheduled-change rate), held flat for the rest of the horizon --
        # the same "one step, then flat" shape rmd.py's own 73->75 step
        # uses.
        **{year: _2026_BRACKETS for year in range(_DOCUMENTED_YEARS.start, 2027)},
        **{year: _2027_BRACKETS for year in range(2027, _DOCUMENTED_YEARS.stop)},
    },
    citation="SC Code Ann. §12-6-510 (placeholder — pending verification; 2027 top rate is illustrative)",
    last_verified=date(2026, 8, 27),
    verified=False,
)

_AGE_65_EXCLUSION = SourcedFigure(
    name="sc_age_65_exclusion",
    schedule={year: 15_000.0 for year in _DOCUMENTED_YEARS},
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
    state_tax_owed, bracket_breakdown = apply_progressive_brackets_detailed(taxable_income, brackets)

    return StateTaxResult(
        state="SC",
        state_tax_owed=state_tax_owed,
        figures_used=figures_used,
        taxable_income=taxable_income,
        exclusion_applied=total_exclusion,
        bracket_breakdown=bracket_breakdown,
    )
