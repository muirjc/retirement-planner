"""IRMAA (Medicare Income-Related Monthly Adjustment Amount) surcharge
calculation (010-advanced-tax-benefits FR-001-FR-004).

Genuine tiered-threshold lookup against a MAGI figure the caller supplies
(comparison/projection.py assembles it via _approximate_magi() plus the
two-year look-back logic, research.md §§2-3 -- this module has no opinion
about how MAGI was derived, only what tier it falls into).

The dollar tier thresholds and surcharge amounts below are CMS's actual
published tax year 2026 IRMAA figures (Part B + Part D surcharge,
combined into one annual `annual_surcharge_per_person` per tier — this
module has no separate Part B/Part D breakdown), cross-checked directly
against CMS's published tables (014-figure-verification, rp-9wi.3). Note
this also corrects a modeling bug the placeholder figures carried: real
IRMAA surcharge amounts are identical for both filing statuses at the
same relative tier (only the MAGI threshold differs by filing status) —
the old placeholder halved the single-filer surcharge relative to MFJ's,
which was never how IRMAA actually works.

Schedule note: mirroring federal.py's own precedent, these tier tables
are stated in real (inflation-adjusted, "today's dollars") terms with no
further indexing engine, so the same table applies to every documented
year -- repeated across _DOCUMENTED_YEARS rather than genuinely varying
per year.

See specs/010-advanced-tax-benefits/contracts/tax-api.md for the locked
public signature of compute_irmaa_surcharge().
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from .models import FilingStatus, IrmaaResult, IrmaaTierRow, IrmaaTierTable, SourcedFigure

_DOCUMENTED_YEARS = range(2020, 2075)

_MFJ_TIERS: IrmaaTierTable = (
    IrmaaTierRow(magi_threshold=218_000.0, annual_surcharge_per_person=1_148.40),
    IrmaaTierRow(magi_threshold=274_000.0, annual_surcharge_per_person=2_884.80),
    IrmaaTierRow(magi_threshold=342_000.0, annual_surcharge_per_person=4_620.00),
    IrmaaTierRow(magi_threshold=410_000.0, annual_surcharge_per_person=6_355.20),
    IrmaaTierRow(magi_threshold=750_000.0, annual_surcharge_per_person=6_936.00),
)

_SINGLE_TIERS: IrmaaTierTable = (
    IrmaaTierRow(magi_threshold=109_000.0, annual_surcharge_per_person=1_148.40),
    IrmaaTierRow(magi_threshold=137_000.0, annual_surcharge_per_person=2_884.80),
    IrmaaTierRow(magi_threshold=171_000.0, annual_surcharge_per_person=4_620.00),
    IrmaaTierRow(magi_threshold=205_000.0, annual_surcharge_per_person=6_355.20),
    IrmaaTierRow(magi_threshold=500_000.0, annual_surcharge_per_person=6_936.00),
)

_IRMAA_TIERS: dict[FilingStatus, SourcedFigure[IrmaaTierTable]] = {
    "married_filing_jointly": SourcedFigure(
        name="irmaa_tiers_mfj",
        schedule={year: _MFJ_TIERS for year in _DOCUMENTED_YEARS},
        citation="CMS.gov, 2026 Medicare Parts B & D IRMAA tables (CMS-8089-N/8090-N/8091-N), MFJ schedule",
        last_verified=date(2026, 8, 30),
        verified=True,
    ),
    "single": SourcedFigure(
        name="irmaa_tiers_single",
        schedule={year: _SINGLE_TIERS for year in _DOCUMENTED_YEARS},
        citation="CMS.gov, 2026 Medicare Parts B & D IRMAA tables (CMS-8089-N/8090-N/8091-N), single schedule",
        last_verified=date(2026, 8, 30),
        verified=True,
    ),
}


def compute_irmaa_surcharge(
    magi: float,
    income_basis: Literal["two_year_lookback", "current_year_proxy"],
    filing_status: FilingStatus,
    tax_year: int,
    enrolled_member_count: int,
) -> IrmaaResult:
    """Looks up tax_year's IRMAA tier table for filing_status and finds
    the highest tier whose magi_threshold is <= magi (inclusive lower
    bound, Edge Cases) (FR-001). Returns surcharge_owed as
    annual_surcharge_per_person * enrolled_member_count (FR-002, FR-003).
    Returns tier_crossed=None and surcharge_owed=0.0 when magi is below
    every documented tier, and unconditionally when
    enrolled_member_count <= 0 (FR-004) -- never raises for "no surcharge
    applies," only for an undocumented tax_year. Raises
    UnsupportedTaxYearError if the tier table has no entry for tax_year.
    """
    tier_figure = _IRMAA_TIERS[filing_status]
    table = tier_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used = [tier_figure.usage_for_year(tax_year)]

    if enrolled_member_count <= 0:
        return IrmaaResult(
            magi=magi,
            income_basis=income_basis,
            tier_crossed=None,
            enrolled_member_count=enrolled_member_count,
            surcharge_owed=0.0,
            figures_used=figures_used,
        )

    applicable_tier: IrmaaTierRow | None = None
    for row in table:
        if magi >= row.magi_threshold:
            applicable_tier = row

    if applicable_tier is None:
        return IrmaaResult(
            magi=magi,
            income_basis=income_basis,
            tier_crossed=None,
            enrolled_member_count=enrolled_member_count,
            surcharge_owed=0.0,
            figures_used=figures_used,
        )

    return IrmaaResult(
        magi=magi,
        income_basis=income_basis,
        tier_crossed=applicable_tier.magi_threshold,
        enrolled_member_count=enrolled_member_count,
        surcharge_owed=applicable_tier.annual_surcharge_per_person * enrolled_member_count,
        figures_used=figures_used,
    )
