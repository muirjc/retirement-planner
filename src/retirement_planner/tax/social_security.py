"""Federal Social Security taxability (FR-002).

Implements the real provisional-income formula (26 U.S.C. §86): 0%, up to
50%, or up to 85% of a household's Social Security benefit is included in
taxable income depending on provisional income (ordinary income + half the
gross benefit) relative to two filing-status-specific thresholds — replacing
the prototype's flat 85%-inclusion shortcut the source requirement document
flags as a known accuracy gap.

The $32,000/$44,000 (MFJ) and $25,000/$34,000 (single) thresholds are the
actual, longstanding statutory base amounts and have not changed since 1983
— confirmed directly against 26 U.S.C. §86(c)(1)-(2)'s text
(014-figure-verification, rp-9wi.6), hence `verified=True` below.

Schedule note (added for 004-strategy-comparison-layer): these thresholds
are not inflation-indexed by statute (unlike federal brackets), so the same
dollar figures apply to every documented year — the schedule below repeats
them across `_DOCUMENTED_YEARS` rather than adding a genuinely new value
per year, so a multi-year caller (a full-horizon projection) does not hit
`UnsupportedTaxYearError` for every year after 2026.

See specs/002-tax-calculation-engine/contracts/tax-api.md ("Operations"
section) for the locked public signature of compute_taxable_social_security().
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import FigureUsage, FilingStatus, IncomeComponents, SourcedFigure

_DOCUMENTED_YEARS = range(2020, 2075)


@dataclass
class _ProvisionalIncomeThresholds:
    threshold_1: float
    """Below this, none of the Social Security benefit is taxable."""
    threshold_2: float
    """Above this, up to 85% of the benefit is taxable."""


_THRESHOLDS: dict[FilingStatus, SourcedFigure[_ProvisionalIncomeThresholds]] = {
    "married_filing_jointly": SourcedFigure(
        name="ss_provisional_income_thresholds_mfj",
        schedule={
            year: _ProvisionalIncomeThresholds(threshold_1=32_000.0, threshold_2=44_000.0)
            for year in _DOCUMENTED_YEARS
        },
        citation="26 U.S.C. §86(c)(1)(B), (c)(2)(B) — MFJ base and adjusted base amounts",
        last_verified=date(2026, 8, 30),
        verified=True,
    ),
    "single": SourcedFigure(
        name="ss_provisional_income_thresholds_single",
        schedule={
            year: _ProvisionalIncomeThresholds(threshold_1=25_000.0, threshold_2=34_000.0)
            for year in _DOCUMENTED_YEARS
        },
        citation="26 U.S.C. §86(c)(1)(A), (c)(2)(A) — single filer base and adjusted base amounts",
        last_verified=date(2026, 8, 30),
        verified=True,
    ),
}


def compute_taxable_social_security(
    income: IncomeComponents,
    filing_status: FilingStatus,
    tax_year: int,
) -> tuple[float, list[FigureUsage]]:
    """Returns (taxable_social_security, figures_used) per the federal
    provisional-income rule (FR-002). Raises UnsupportedTaxYearError if the
    threshold figures have no entry for tax_year.
    """
    figure = _THRESHOLDS[filing_status]
    thresholds = figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used = [figure.usage_for_year(tax_year)]

    benefit = income.social_security_gross_benefit
    provisional_income = income.ordinary_income + 0.5 * benefit

    if provisional_income <= thresholds.threshold_1:
        taxable = 0.0
    elif provisional_income <= thresholds.threshold_2:
        taxable = min(0.5 * benefit, 0.5 * (provisional_income - thresholds.threshold_1))
    else:
        tier_1_amount = min(0.5 * benefit, 0.5 * (thresholds.threshold_2 - thresholds.threshold_1))
        taxable = min(
            0.85 * benefit,
            0.85 * (provisional_income - thresholds.threshold_2) + tier_1_amount,
        )

    return taxable, figures_used
