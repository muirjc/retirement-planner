"""NIIT (Net Investment Income Tax) calculation
(010-advanced-tax-benefits FR-005-FR-007).

A flat-rate surtax applied once a household's MAGI exceeds a
filing-status threshold, and then only to the lesser of the household's
investment income or the amount MAGI exceeds the threshold by -- the
same bound IRC §1411 itself uses, never the full investment income once
any threshold is crossed (data-model.md § Validation rules).

The threshold dollar figure and the 3.8% rate below are illustrative
placeholders, not asserted as IRC §1411's actual current figures -- see
quickstart.md and this project's own established precedent (federal.py's
identical disclosure for its own bracket tables). `verified=False`
reflects that honestly (research.md §7).

What counts as "investment income" here is this feature's own documented
approximation (research.md §1: the taxable-account withdrawal amount for
the plan year, since this engine tracks no cost basis) -- computed by
the caller (comparison/projection.py) and passed in; this module has no
opinion about how investment_income was derived, only how the surtax
applies to it once given.

See specs/010-advanced-tax-benefits/contracts/tax-api.md for the locked
public signature of compute_niit().
"""

from __future__ import annotations

from datetime import date

from .models import FigureUsage, FilingStatus, NiitResult, SourcedFigure

_DOCUMENTED_YEARS = range(2020, 2075)

_NIIT_THRESHOLDS: dict[FilingStatus, SourcedFigure[float]] = {
    "married_filing_jointly": SourcedFigure(
        name="niit_threshold_mfj",
        schedule={year: 250_000.0 for year in _DOCUMENTED_YEARS},
        citation="IRC §1411, MFJ threshold (placeholder — pending verification)",
        last_verified=date(2026, 8, 28),
        verified=False,
    ),
    "single": SourcedFigure(
        name="niit_threshold_single",
        schedule={year: 200_000.0 for year in _DOCUMENTED_YEARS},
        citation="IRC §1411, single threshold (placeholder — pending verification)",
        last_verified=date(2026, 8, 28),
        verified=False,
    ),
}

_NIIT_RATE: SourcedFigure[float] = SourcedFigure(
    name="niit_rate",
    schedule={year: 0.038 for year in _DOCUMENTED_YEARS},
    citation="IRC §1411, surtax rate (placeholder — pending verification)",
    last_verified=date(2026, 8, 28),
    verified=False,
)


def compute_niit(
    magi: float,
    investment_income: float,
    filing_status: FilingStatus,
    tax_year: int,
) -> NiitResult:
    """Looks up tax_year's NIIT threshold for filing_status and the
    surtax rate, and applies the rate to min(investment_income,
    magi - threshold) once magi exceeds the threshold (FR-005-FR-007) --
    "exceeds" is strict (magi == threshold does not trigger it, Edge
    Cases). Returns threshold_exceeded=False and surtax_owed=0.0
    otherwise. Raises UnsupportedTaxYearError if either figure has no
    entry for tax_year.
    """
    threshold_figure = _NIIT_THRESHOLDS[filing_status]
    threshold = threshold_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    rate = _NIIT_RATE.value_for_year(tax_year)
    figures_used: list[FigureUsage] = [
        threshold_figure.usage_for_year(tax_year),
        _NIIT_RATE.usage_for_year(tax_year),
    ]

    if magi <= threshold:
        return NiitResult(
            magi=magi,
            investment_income=investment_income,
            threshold_exceeded=False,
            surtax_owed=0.0,
            figures_used=figures_used,
        )

    taxable_amount = min(investment_income, magi - threshold)
    return NiitResult(
        magi=magi,
        investment_income=investment_income,
        threshold_exceeded=True,
        surtax_owed=taxable_amount * rate,
        figures_used=figures_used,
    )
