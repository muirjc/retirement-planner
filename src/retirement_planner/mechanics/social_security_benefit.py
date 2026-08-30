"""Social Security claiming-age benefit adjustment
(016-ss-claiming-age-actuarial-adjustment, rp-n44).

Derives the annual Social Security benefit actually paid at a household
member's chosen claiming age, given their Primary Insurance Amount (PIA --
the benefit payable if claimed exactly at their full retirement age, FRA)
and FRA itself. Before this feature, every engine path used a member's
configured benefit flat, regardless of claiming age -- so the claiming-age
comparison grid mechanically favored claiming as early as possible, the
exact naive framing real Social Security claiming analysis exists to
correct (spec.md, research.md Decision 1).

Early-claiming reduction and delayed-retirement-credit rates cross-checked
directly against 20 C.F.R. §404.410 (early reduction) and §404.313
(delayed credit) -- the current e-CFR text, via Cornell LII's mirror
(016-ss-claiming-age-actuarial-adjustment, implementation-time
verification) -- hence `verified=True` below. These per-month rates are
fixed by regulation, not annually revised (20 C.F.R. §404.313 applies its
2/3-of-1%-per-month rate to everyone born in 1943 or later -- i.e.,
everyone this tool's claiming-age range of 62-70 can otherwise apply to
today or for the foreseeable future), so the schedule below repeats the
same rate set across `_DOCUMENTED_YEARS`, mirroring
tax/social_security.py's own "fixed since 1983" provisional-income
thresholds and mechanics/rmd.py's UNIFORM_LIFETIME_TABLE.

Months-early/months-delayed are computed as a continuous linear function
of claiming_age and full_retirement_age (both of which this engine allows
to carry a fractional-year FRA, but only a whole-year claiming_age) rather
than SSA's own whole-month administrative processing -- a documented
simplification (Principle I), not silently absorbed: this engine has no
notion of a mid-year claim date, only a claiming *age* in whole years, so
"months early/delayed" here is exactly (claiming_age - full_retirement_age)
* 12, not a real calendar-month count.

See contracts/mechanics-api.md ("New operations (social_security_benefit)"
section) for the locked public signature of compute_social_security_benefit().
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from retirement_planner.tax import SourcedFigure

from .models import SocialSecurityBenefitResult

_DOCUMENTED_YEARS = range(2020, 2075)


@dataclass
class _ClaimingAgeAdjustmentRates:
    early_reduction_rate_tier_1: float
    """Per month, for each of the first 36 months claimed before FRA."""
    early_reduction_rate_tier_2: float
    """Per month, for each additional month claimed before FRA beyond the
    first 36."""
    early_reduction_tier_1_months: int
    """36 -- the boundary between the two early-reduction rates above."""
    delayed_credit_rate_per_month: float
    """Per month, for each month claimed after FRA, up to
    max_claiming_age_for_credit."""
    max_claiming_age_for_credit: int
    """70 -- no further delayed retirement credit accrues past this age."""


_RATES = _ClaimingAgeAdjustmentRates(
    early_reduction_rate_tier_1=(5 / 9) / 100,  # 5/9 of 1% per month
    early_reduction_rate_tier_2=(5 / 12) / 100,  # 5/12 of 1% per month
    early_reduction_tier_1_months=36,
    delayed_credit_rate_per_month=(2 / 3) / 100,  # 2/3 of 1% per month
    max_claiming_age_for_credit=70,
)

SS_CLAIMING_AGE_ADJUSTMENT: SourcedFigure[_ClaimingAgeAdjustmentRates] = SourcedFigure(
    name="ss_claiming_age_adjustment_rates",
    schedule={year: _RATES for year in _DOCUMENTED_YEARS},
    citation=(
        "42 U.S.C. §402(q) (early retirement reduction), §402(w) (delayed retirement credit); "
        "20 C.F.R. §404.410 (5/9 of 1% per month for the first 36 months claimed early, "
        "5/12 of 1% per month beyond that) and §404.313 (2/3 of 1% per month delayed retirement "
        "credit, for anyone born in 1943 or later, from full retirement age through age 70)"
    ),
    last_verified=date(2026, 8, 30),
    verified=True,
)


def compute_social_security_benefit(
    primary_insurance_amount: float,
    full_retirement_age: float,
    claiming_age: int,
    tax_year: int,
) -> SocialSecurityBenefitResult:
    """Derives the annual benefit actually paid at claiming_age, given a
    member's PIA and FRA (FR-002-FR-005). claiming_age exactly equal to
    full_retirement_age returns annual_benefit == primary_insurance_amount,
    adjustment_factor == 1.0. claiming_age below full_retirement_age
    applies the tiered early-reduction formula; above it applies the
    delayed retirement credit, capped at max_claiming_age_for_credit.

    Raises UnsupportedTaxYearError if the adjustment-rate figure has no
    schedule entry for tax_year. Does not itself validate claiming_age's
    62-70 range -- callers rely on scenario.validation.validate() for
    that, as compute_rmd() and compute_taxable_social_security() already
    do for their own inputs.
    """
    figure = SS_CLAIMING_AGE_ADJUSTMENT
    rates = figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used = [figure.usage_for_year(tax_year)]

    months_from_fra = (claiming_age - full_retirement_age) * 12.0

    if months_from_fra < 0:
        months_early = -months_from_fra
        tier_1_months = min(months_early, rates.early_reduction_tier_1_months)
        tier_2_months = max(0.0, months_early - rates.early_reduction_tier_1_months)
        reduction = tier_1_months * rates.early_reduction_rate_tier_1 + tier_2_months * rates.early_reduction_rate_tier_2
        adjustment_factor = 1.0 - reduction
    elif months_from_fra > 0:
        capped_claiming_age = min(claiming_age, rates.max_claiming_age_for_credit)
        months_delayed = max(0.0, (capped_claiming_age - full_retirement_age) * 12.0)
        adjustment_factor = 1.0 + months_delayed * rates.delayed_credit_rate_per_month
    else:
        adjustment_factor = 1.0

    return SocialSecurityBenefitResult(
        annual_benefit=primary_insurance_amount * adjustment_factor,
        adjustment_factor=adjustment_factor,
        figures_used=figures_used,
    )
