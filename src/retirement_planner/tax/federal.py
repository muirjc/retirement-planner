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

The bracket dollar thresholds below are illustrative placeholders (round
numbers in the right order of magnitude), not asserted as the actual IRS
Rev. Proc. 2026 figures — see quickstart.md and plan.md's Development
Workflow gate. `verified=False` reflects that honestly; replacing these with
real, cited figures is follow-on work, not a gap this feature hides.

See specs/002-tax-calculation-engine/contracts/tax-api.md ("Operations"
section) for the locked public signature of compute_federal_tax().
"""

from __future__ import annotations

from datetime import date

from .bracket_math import apply_progressive_brackets
from .models import BracketRow, BracketTable, FederalTaxResult, FilingStatus, IncomeComponents, SourcedFigure
from .social_security import compute_taxable_social_security

_FEDERAL_BRACKETS: dict[FilingStatus, SourcedFigure[BracketTable]] = {
    "married_filing_jointly": SourcedFigure(
        name="federal_brackets_mfj",
        schedule={
            2026: (
                BracketRow(rate=0.10, income_up_to=24_000.0),
                BracketRow(rate=0.12, income_up_to=96_000.0),
                BracketRow(rate=0.22, income_up_to=206_000.0),
                BracketRow(rate=0.24, income_up_to=394_000.0),
                BracketRow(rate=0.32, income_up_to=500_000.0),
                BracketRow(rate=0.35, income_up_to=750_000.0),
                BracketRow(rate=0.37, income_up_to=None),
            ),
        },
        citation="IRS Rev. Proc. 2026-XX, MFJ schedule (placeholder — pending verification)",
        last_verified=date(2026, 8, 27),
        verified=False,
    ),
    "single": SourcedFigure(
        name="federal_brackets_single",
        schedule={
            2026: (
                BracketRow(rate=0.10, income_up_to=12_000.0),
                BracketRow(rate=0.12, income_up_to=48_000.0),
                BracketRow(rate=0.22, income_up_to=103_000.0),
                BracketRow(rate=0.24, income_up_to=197_000.0),
                BracketRow(rate=0.32, income_up_to=250_000.0),
                BracketRow(rate=0.35, income_up_to=625_000.0),
                BracketRow(rate=0.37, income_up_to=None),
            ),
        },
        citation="IRS Rev. Proc. 2026-XX, single schedule (placeholder — pending verification)",
        last_verified=date(2026, 8, 27),
        verified=False,
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
