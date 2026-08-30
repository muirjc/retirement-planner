"""Federal income tax calculation (FR-001, FR-003).

Genuine progressive bracket math against a federal bracket table, applied to
taxable income = ordinary income + the taxable portion of Social Security
(social_security.compute_taxable_social_security()).

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

from .bracket_math import apply_progressive_brackets
from .models import BracketRow, BracketTable, FederalTaxResult, FilingStatus, IncomeComponents, SourcedFigure
from .social_security import compute_taxable_social_security

_DOCUMENTED_YEARS = range(2020, 2075)

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


def compute_federal_tax(
    income: IncomeComponents,
    filing_status: FilingStatus,
    tax_year: int,
) -> FederalTaxResult:
    """Computes federal tax via compute_taxable_social_security() + genuine
    progressive bracket math against tax_year's federal brackets (FR-001).
    Raises UnsupportedTaxYearError if any figure needed (SS thresholds or
    federal brackets) has no entry for tax_year.
    """
    taxable_social_security, figures_used = compute_taxable_social_security(income, filing_status, tax_year)

    bracket_figure = _FEDERAL_BRACKETS[filing_status]
    brackets = bracket_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used = [*figures_used, bracket_figure.usage_for_year(tax_year)]

    taxable_income = income.ordinary_income + taxable_social_security
    federal_tax_owed = apply_progressive_brackets(taxable_income, brackets)

    return FederalTaxResult(
        federal_tax_owed=federal_tax_owed,
        taxable_social_security=taxable_social_security,
        figures_used=figures_used,
    )
