"""Social Security claiming-age, spousal, and survivor benefit adjustment
(016-ss-claiming-age-actuarial-adjustment, rp-n44; extended by
017-ss-spousal-survivor-benefits, rp-52n).

Derives the annual Social Security benefit actually paid at a household
member's chosen claiming age, given their Primary Insurance Amount (PIA --
the benefit payable if claimed exactly at their full retirement age, FRA)
and FRA itself. Before this feature, every engine path used a member's
configured benefit flat, regardless of claiming age -- so the claiming-age
comparison grid mechanically favored claiming as early as possible, the
exact naive framing real Social Security claiming analysis exists to
correct (spec.md, research.md Decision 1).

017-ss-spousal-survivor-benefits adds two further, related operations to
this same module rather than a new sibling one (research.md Decision 1
there): compute_spousal_benefit_floor() (a lower-earning spouse's benefit
floor, up to 50% of the other spouse's PIA) and compute_survivor_benefit()
(the "higher of the two continues, the lower stops" rule after one
spouse's death) -- both share this module's PIA/FRA/claiming-age-keyed,
SourcedFigure-cited shape, and 42 U.S.C. §402 covers old-age, wife's/
husband's, and widow's/widower's benefits together, the same way 20
C.F.R. §404.410 (already cited below) covers the reduction formula for
all of them in one section.

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

from .models import SocialSecurityBenefitResult, SpousalBenefitResult, SurvivorBenefitResult

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


@dataclass
class _SpousalAdjustmentRates:
    early_reduction_rate_tier_1: float
    """Per month, for each of the first 36 months a spousal amount is
    claimed before the claiming member's own FRA -- 25/36 of 1%, a
    different (larger) rate than compute_social_security_benefit()'s own
    worker-benefit tier-1 rate (5/9 of 1%)."""
    early_reduction_rate_tier_2: float
    """Per month, for each additional month claimed before FRA beyond the
    first 36 -- 5/12 of 1%, the same tier-2 rate the worker-benefit table
    already uses."""
    early_reduction_tier_1_months: int
    """36 -- the boundary between the two early-reduction rates above."""


_SPOUSAL_RATES = _SpousalAdjustmentRates(
    early_reduction_rate_tier_1=(25 / 36) / 100,  # 25/36 of 1% per month
    early_reduction_rate_tier_2=(5 / 12) / 100,  # 5/12 of 1% per month
    early_reduction_tier_1_months=36,
)

SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT: SourcedFigure[_SpousalAdjustmentRates] = SourcedFigure(
    name="ss_spousal_claiming_age_adjustment_rates",
    schedule={year: _SPOUSAL_RATES for year in _DOCUMENTED_YEARS},
    citation=(
        "42 U.S.C. §402(b) (wife's insurance benefits), §402(c) (husband's insurance benefits); "
        "20 C.F.R. §404.410 (wife's/husband's benefit reduction: 25/36 of 1% per month for the "
        "first 36 months claimed early, 5/12 of 1% per month beyond that -- no delayed-retirement "
        "credit applies to a spousal amount)"
    ),
    last_verified=date(2026, 8, 31),
    verified=True,
)


def compute_spousal_benefit_floor(
    other_member_pia: float,
    full_retirement_age: float,
    claiming_age: int,
    tax_year: int,
) -> SpousalBenefitResult:
    """Derives the spousal-derived amount available to a member claiming
    at claiming_age relative to their OWN full_retirement_age, based on
    the OTHER member's raw PIA (017-ss-spousal-survivor-benefits FR-001,
    FR-003). Returns spousal_amount == 0.5 * other_member_pia,
    adjustment_factor == 1.0 for claiming_age >= full_retirement_age --
    no delayed-retirement credit applies to a spousal amount, ever.
    Applies the tiered spousal early-reduction formula (distinct from
    compute_social_security_benefit()'s own worker-benefit rate) when
    claiming_age < full_retirement_age. Raises UnsupportedTaxYearError if
    the adjustment-rate figure has no schedule entry for tax_year. Does
    not itself validate claiming_age's 62-70 range, consistent with
    compute_social_security_benefit().
    """
    figure = SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT
    rates = figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used = [figure.usage_for_year(tax_year)]

    months_early = max(0.0, (full_retirement_age - claiming_age) * 12.0)
    if months_early > 0:
        tier_1_months = min(months_early, rates.early_reduction_tier_1_months)
        tier_2_months = max(0.0, months_early - rates.early_reduction_tier_1_months)
        reduction = tier_1_months * rates.early_reduction_rate_tier_1 + tier_2_months * rates.early_reduction_rate_tier_2
        adjustment_factor = 1.0 - reduction
    else:
        # At or after FRA: capped at exactly 50% -- no delayed-retirement
        # credit on a spousal amount, unlike the worker's own benefit.
        adjustment_factor = 1.0

    spousal_base = 0.5 * other_member_pia
    return SpousalBenefitResult(
        spousal_amount=spousal_base * adjustment_factor,
        adjustment_factor=adjustment_factor,
        figures_used=figures_used,
    )


SS_SURVIVOR_BENEFIT_RULE: SourcedFigure[None] = SourcedFigure(
    name="ss_survivor_benefit_rule",
    schedule={year: None for year in _DOCUMENTED_YEARS},
    citation=(
        "42 U.S.C. §402(e)/(f) (widow's/widower's insurance benefits); 20 C.F.R. §404.335/"
        "§404.336 -- the surviving spouse's benefit is the higher of the two spouses' own "
        "benefit amounts; this feature does not model the widow(er)'s-own early-claiming "
        "reduction or the statutory 'widow's limit' cap (spec.md Assumptions, a documented "
        "simplification)"
    ),
    last_verified=date(2026, 8, 31),
    verified=True,
)


def compute_survivor_benefit(
    member_a_benefit: float,
    member_b_benefit: float,
    tax_year: int,
) -> SurvivorBenefitResult:
    """Returns the higher of the two currently-claimed benefit amounts as
    the survivor's ongoing benefit (017-ss-spousal-survivor-benefits
    FR-005) -- the caller is responsible for attributing this amount to
    whichever member is actually still living; the result does not
    depend on which one that is (research.md Decision 4: this function
    takes no "which member died" argument, since max() is symmetric).
    Raises UnsupportedTaxYearError if SS_SURVIVOR_BENEFIT_RULE has no
    schedule entry for tax_year (in practice never, given
    _DOCUMENTED_YEARS' range -- consulted purely for the citation trail,
    mirroring every other SourcedFigure-backed operation in this
    codebase).
    """
    figure = SS_SURVIVOR_BENEFIT_RULE
    figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used = [figure.usage_for_year(tax_year)]

    return SurvivorBenefitResult(
        survivor_benefit=max(member_a_benefit, member_b_benefit),
        figures_used=figures_used,
    )
