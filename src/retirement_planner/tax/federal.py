"""Federal income tax calculation (FR-001, FR-003).

Genuine progressive bracket math against a federal bracket table, applied to
taxable income = (ordinary income + the taxable portion of Social Security
(social_security.compute_taxable_social_security())) minus the standard
deduction (26 U.S.C. §63(c), including the age-65 addition under §63(f);
rp-7me) -- floored at $0, never negative.

Bracket edges are expressed in a single, explicit basis — today's real
(inflation-adjusted) dollars, consistent with the rest of this tool's "_real"
convention (e.g. Scenario.spending.annual_need_real from
001-scenario-config-management) — rather than a separate nominal-dollar
projection. This is the "explicit, documented inflation-indexing assumption"
FR-003 requires: the assumption is "real terms, no further indexing engine,"
stated here rather than left implicit.

The bracket dollar thresholds below are IRS Rev. Proc. 2025-32's actual
tax year 2026 figures, cross-checked directly against that Revenue
Procedure (014-figure-verification, rp-9wi.1) — the tax year they were
pinned to is fixed by this feature's own "real dollars, no further
indexing engine" design (above), not by whatever the current calendar
year happens to be when this module is read.

Schedule note (added for 004-strategy-comparison-layer): since these edges
are already stated to be real (inflation-adjusted) dollars with "no further
indexing engine," the same bracket table applies to every documented year —
the schedule below repeats it across `_DOCUMENTED_YEARS` rather than adding
a genuinely new table per year, so a multi-year caller (a full-horizon
projection) does not hit `UnsupportedTaxYearError` for every year after
2026.

See specs/002-tax-calculation-engine/contracts/tax-api.md ("Operations"
section) for the locked public signature of compute_federal_tax().
"""

from __future__ import annotations

from datetime import date

from .bracket_math import apply_progressive_brackets_detailed
from .models import (
    BracketRow,
    BracketTable,
    FederalTaxResult,
    FigureUsage,
    FilingStatus,
    IncomeComponents,
    SourcedFigure,
    StandardDeductionAmounts,
)
from .social_security import compute_taxable_social_security

_DOCUMENTED_YEARS = range(2020, 2075)

_AGE_65_THRESHOLD = 65

_MFJ_BRACKETS: BracketTable = (
    BracketRow(rate=0.10, income_up_to=24_800.0),
    BracketRow(rate=0.12, income_up_to=100_800.0),
    BracketRow(rate=0.22, income_up_to=211_400.0),
    BracketRow(rate=0.24, income_up_to=403_550.0),
    BracketRow(rate=0.32, income_up_to=512_450.0),
    BracketRow(rate=0.35, income_up_to=768_700.0),
    BracketRow(rate=0.37, income_up_to=None),
)

_SINGLE_BRACKETS: BracketTable = (
    BracketRow(rate=0.10, income_up_to=12_400.0),
    BracketRow(rate=0.12, income_up_to=50_400.0),
    BracketRow(rate=0.22, income_up_to=105_700.0),
    BracketRow(rate=0.24, income_up_to=201_775.0),
    BracketRow(rate=0.32, income_up_to=256_225.0),
    BracketRow(rate=0.35, income_up_to=640_600.0),
    BracketRow(rate=0.37, income_up_to=None),
)

_FEDERAL_BRACKETS: dict[FilingStatus, SourcedFigure[BracketTable]] = {
    "married_filing_jointly": SourcedFigure(
        name="federal_brackets_mfj",
        schedule={year: _MFJ_BRACKETS for year in _DOCUMENTED_YEARS},
        citation="IRS Rev. Proc. 2025-32 §2.01, tax year 2026 married filing jointly schedule",
        last_verified=date(2026, 8, 30),
        verified=True,
    ),
    "single": SourcedFigure(
        name="federal_brackets_single",
        schedule={year: _SINGLE_BRACKETS for year in _DOCUMENTED_YEARS},
        citation="IRS Rev. Proc. 2025-32 §2.01, tax year 2026 single filer schedule",
        last_verified=date(2026, 8, 30),
        verified=True,
    ),
}

# Standard deduction (26 U.S.C. §63(c)) -- rp-7me: taxable_income below was
# previously ordinary income + taxable Social Security with nothing
# subtracted before bracket application, overstating federal tax owed in
# every scenario. `base` is IRS Rev. Proc. 2025-32's tax year 2026 amount;
# `additional_per_filer_65_plus` is added once per household member who has
# reached age 65 that year (26 U.S.C. §63(f)) -- same "real dollars, no
# further indexing engine" convention as _FEDERAL_BRACKETS above, held flat
# across every documented year rather than re-indexed annually.
_MFJ_STANDARD_DEDUCTION = StandardDeductionAmounts(base=32_200.0, additional_per_filer_65_plus=1_650.0)
_SINGLE_STANDARD_DEDUCTION = StandardDeductionAmounts(base=16_100.0, additional_per_filer_65_plus=2_050.0)

_STANDARD_DEDUCTIONS: dict[FilingStatus, SourcedFigure[StandardDeductionAmounts]] = {
    "married_filing_jointly": SourcedFigure(
        name="standard_deduction_mfj",
        schedule={year: _MFJ_STANDARD_DEDUCTION for year in _DOCUMENTED_YEARS},
        citation=(
            "IRS Rev. Proc. 2025-32 §4.14(1), tax year 2026 standard deduction "
            "(married filing jointly, base + aged-65 addition per filer)"
        ),
        last_verified=date(2026, 8, 30),
        verified=True,
    ),
    "single": SourcedFigure(
        name="standard_deduction_single",
        schedule={year: _SINGLE_STANDARD_DEDUCTION for year in _DOCUMENTED_YEARS},
        citation=(
            "IRS Rev. Proc. 2025-32 §4.14(1), tax year 2026 standard deduction "
            "(single filer, base + aged-65 addition)"
        ),
        last_verified=date(2026, 8, 30),
        verified=True,
    ),
}


def _standard_deduction_for(
    filing_status: FilingStatus,
    tax_year: int,
    filer_ages: list[int],
) -> tuple[float, FigureUsage]:
    """rp-nui: factored out of compute_federal_tax() below so
    bracket_ceiling_for_rate() can share the exact same standard-deduction
    computation rather than duplicating it -- base + the age-65 addition
    (26 U.S.C. §63(f)) once per qualifying filer. Behavior is byte-identical
    to what compute_federal_tax() computed inline before this refactor.
    Raises UnsupportedTaxYearError if tax_year has no schedule entry.
    """
    deduction_figure = _STANDARD_DEDUCTIONS[filing_status]
    deduction_amounts = deduction_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    standard_deduction = deduction_amounts.base + sum(
        deduction_amounts.additional_per_filer_65_plus for age in filer_ages if age >= _AGE_65_THRESHOLD
    )
    return standard_deduction, deduction_figure.usage_for_year(tax_year)


def compute_federal_tax(
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> FederalTaxResult:
    """Computes federal tax via compute_taxable_social_security() + the
    standard deduction (rp-7me) + genuine progressive bracket math against
    tax_year's federal brackets (FR-001). `filer_ages` is one age per
    household member (length 1 for "single", 2 for "married_filing_jointly"
    -- see data-model.md § FilerAges), used only to add the age-65 standard
    deduction addition per qualifying filer; it does not otherwise affect
    the computation. Raises UnsupportedTaxYearError if any figure needed
    (SS thresholds, federal brackets, or the standard deduction) has no
    entry for tax_year.
    """
    taxable_social_security, figures_used = compute_taxable_social_security(income, filing_status, tax_year)

    bracket_figure = _FEDERAL_BRACKETS[filing_status]
    brackets = bracket_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used = [*figures_used, bracket_figure.usage_for_year(tax_year)]

    standard_deduction, deduction_usage = _standard_deduction_for(filing_status, tax_year, filer_ages)
    figures_used = [*figures_used, deduction_usage]

    # max(0, ...): the standard deduction shields income, it never turns
    # into a negative taxable-income (let alone a refundable) figure.
    taxable_income = max(0.0, income.ordinary_income + taxable_social_security - standard_deduction)
    federal_tax_owed, bracket_breakdown = apply_progressive_brackets_detailed(taxable_income, brackets)

    return FederalTaxResult(
        federal_tax_owed=federal_tax_owed,
        taxable_social_security=taxable_social_security,
        figures_used=figures_used,
        taxable_income=taxable_income,
        standard_deduction_used=standard_deduction,
        bracket_breakdown=bracket_breakdown,
    )


def bracket_ceiling_for_rate(
    rate: float,
    filing_status: FilingStatus,
    tax_year: int,
    filer_ages: list[int],
) -> tuple[float, list[FigureUsage]]:
    """rp-nui: the real dollar ceiling for a NAMED federal bracket
    rate (e.g. 0.22 -> "fill to the top of the 22% bracket"), in the same
    basis mechanics.roth_conversion.fill_to_bracket_ceiling()'s own
    `ceiling` parameter is compared against --
    ordinary_income + taxable_social_security, established BEFORE the
    standard deduction is subtracted.

    _MFJ_BRACKETS/_SINGLE_BRACKETS' own `income_up_to` values are stated
    in compute_federal_tax()'s POST-deduction `taxable_income` basis
    (federal.py:159 above: taxable_income = ordinary_income +
    taxable_social_security - standard_deduction). Naively returning
    income_up_to alone would under-fill every named-bracket conversion by
    exactly the standard deduction (~$32,200 MFJ 2026) -- so this function
    adds the standard deduction back: bracket_row.income_up_to +
    standard_deduction (via the same _standard_deduction_for() helper
    compute_federal_tax() itself uses, so both stay in lockstep by
    construction, not by convention).

    Raises ValueError if no row's `rate` field exactly matches `rate`
    (e.g. 0.23 -- no fuzzy/nearest-rate matching, a mistyped rate fails
    loudly) or if the matching row is the unbounded top bracket
    (income_up_to=None -- "ceiling of an unbounded bracket" is not a
    finite number). Raises UnsupportedTaxYearError if tax_year has no
    bracket-table/standard-deduction entry (mirrors compute_federal_tax()).
    """
    bracket_figure = _FEDERAL_BRACKETS[filing_status]
    brackets = bracket_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    bracket_usage = bracket_figure.usage_for_year(tax_year)

    matching_row = next((row for row in brackets if row.rate == rate), None)
    if matching_row is None:
        raise ValueError(f"no {filing_status!r} bracket for tax_year {tax_year} has rate {rate!r}")
    if matching_row.income_up_to is None:
        raise ValueError(f"rate {rate!r} is the unbounded top bracket for {filing_status!r} in {tax_year} -- no finite ceiling exists")

    standard_deduction, deduction_usage = _standard_deduction_for(filing_status, tax_year, filer_ages)  # raises UnsupportedTaxYearError
    ceiling = matching_row.income_up_to + standard_deduction
    return ceiling, [bracket_usage, deduction_usage]
