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

025-ss-earnings-test (rp-acq) adds a third, related pair of operations here rather than a new
sibling module (research.md Decision 1): compute_earnings_test_withholding() (SSA's retirement
earnings test -- benefit withheld above an annual exempt-earnings threshold for a member claiming
before their own FRA while still earning) and compute_earnings_test_recredit() (SSA's Adjustment of
the Reduction Factor, ARF -- the withheld total is not a permanent loss, it permanently raises the
benefit from FRA forward). Both are evaluated per member, against that member's own earned income
only (never household-combined, mirroring this module's existing per-member shape). Like
017-ss-spousal-survivor-benefits' own additions, this shares 016's PIA/FRA/claiming-age-keyed,
SourcedFigure-cited shape -- 42 U.S.C. §403 (earnings test) and §402(q) (early-claiming reduction,
already cited above) are administered by SSA as one continuous "what does this claim actually pay"
question, and ARF is explicitly a recalculation of the exact same reduction factor this module
already computes, not a separate formula.

This engine's whole-plan-year granularity (no mid-year claim date, ages and claiming in whole years
only -- see above) forces two further documented simplifications specific to the earnings test,
detailed in each function's own docstring and 025's research.md Decisions 3-4: (1) a member's
FRA-attainment year -- the one plan year SSA's more lenient higher-threshold, $1-for-$3 rule applies
to -- is tested against that member's *entire* year of earned income, not just earnings before their
FRA birthday month; (2) the ARF recredit is tracked in whole "deduction months" (a month with any
withholding, even partial, credits as one full month, per SSA POMS RS 00615.482), capped so the
recredit can restore at most 100% of PIA -- it eliminates early-claiming reduction, it does not
manufacture delayed-retirement credit (POMS RS 00615.480).

See contracts/mechanics-api.md ("New operations (social_security_benefit)"
section) for the locked public signature of compute_social_security_benefit().
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from retirement_planner.tax import SourcedFigure

from .models import (
    EarningsTestRecreditResult,
    EarningsTestWithholdingResult,
    SocialSecurityBenefitResult,
    SpousalBenefitResult,
    SurvivorBenefitResult,
)

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


@dataclass
class _EarningsTestRates:
    withholding_ratio_below_fra: float
    """0.5 -- $1 withheld per $2 earned above the below-FRA exempt
    amount (42 U.S.C. §403(f); 20 C.F.R. §404.434)."""
    withholding_ratio_fra_year: float
    """1/3 -- $1 withheld per $3 earned above the FRA-attainment-year
    exempt amount, the more lenient ratio applying only in the calendar
    year a member reaches FRA."""


_EARNINGS_TEST_RATES = _EarningsTestRates(
    withholding_ratio_below_fra=0.5,
    withholding_ratio_fra_year=1.0 / 3.0,
)

_SSA_EARNINGS_TEST_CITATION = (
    "42 U.S.C. §403(b) (deductions on account of excess earnings), §403(f) (excess-earnings "
    "computation: exempt amount, withholding ratio, and the higher FRA-attainment-year amount "
    "applying only to earnings in months before FRA is reached -- confirmed against Cornell LII's "
    "e-CFR/U.S. Code mirror); 20 C.F.R. §404.430 (monthly and annual exempt amounts defined; excess "
    "earnings defined), §404.434 (excess earnings -- method of charging: $1 withheld per $2 over the "
    "limit before FRA, $1 per $3 in the FRA-attainment year)"
)

SS_EARNINGS_TEST_WITHHOLDING_RATIOS: SourcedFigure[_EarningsTestRates] = SourcedFigure(
    name="ss_earnings_test_withholding_ratios",
    schedule={year: _EARNINGS_TEST_RATES for year in _DOCUMENTED_YEARS},
    citation=_SSA_EARNINGS_TEST_CITATION + " -- ratios fixed by statute, not annually revised.",
    last_verified=date(2026, 9, 3),
    verified=True,
)

SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA: SourcedFigure[float] = SourcedFigure(
    name="ss_earnings_test_exempt_amount_below_fra",
    schedule={year: 24_480.0 for year in _DOCUMENTED_YEARS},
    citation=(
        'SSA, "2026 Cost-of-Living Adjustment (COLA) Fact Sheet" '
        "(https://www.ssa.gov/news/en/cola/factsheets/2026.html): 2026 retirement earnings test "
        "exempt amount for beneficiaries under full retirement age all year, $24,480/yr "
        "($2,040/mo) -- held flat across every documented year (module docstring; this figure is "
        "genuinely wage-indexed and changes annually in reality, mirroring tax/fica.py's "
        "OASDI_WAGE_BASE convention rather than being fixed by statute). " + _SSA_EARNINGS_TEST_CITATION
    ),
    last_verified=date(2026, 9, 3),
    verified=True,
)

SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR: SourcedFigure[float] = SourcedFigure(
    name="ss_earnings_test_exempt_amount_fra_year",
    schedule={year: 65_160.0 for year in _DOCUMENTED_YEARS},
    citation=(
        'SSA, "2026 Cost-of-Living Adjustment (COLA) Fact Sheet" '
        "(https://www.ssa.gov/news/en/cola/factsheets/2026.html): 2026 retirement earnings test "
        "exempt amount for the calendar year a beneficiary reaches full retirement age, "
        "$65,160/yr ($5,430/mo), applying only to earnings in months before FRA is reached -- held "
        "flat across every documented year, same convention as "
        "SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA above. " + _SSA_EARNINGS_TEST_CITATION
    ),
    last_verified=date(2026, 9, 3),
    verified=True,
)


def compute_earnings_test_withholding(
    annual_benefit: float,
    primary_insurance_amount: float,
    earned_income: float,
    is_fra_attainment_year: bool,
    tax_year: int,
) -> EarningsTestWithholdingResult:
    """Applies the SSA retirement earnings test to one member's one plan
    year (025-ss-earnings-test FR-001 through FR-005). annual_benefit is
    that member's own already claiming-age-adjusted benefit for the year
    (compute_social_security_benefit()'s own annual_benefit); this
    function does not itself decide whether the member has claimed or is
    past their FRA-attainment year -- callers only invoke it for a year
    the earnings test can apply to at all (research.md Decision 3).
    primary_insurance_amount is the member's raw PIA, used only to derive
    the monthly-benefit rate for deduction_months_this_year, not to
    recompute the benefit itself. is_fra_attainment_year selects the
    stricter below-FRA threshold/ratio (FR-003) or the more lenient
    FRA-attainment-year threshold/ratio (FR-004) -- this engine has no
    mid-year granularity, so a member's *entire* FRA-attainment-year
    earned income is tested against the lenient rule, not split by month
    (research.md Decision 3). Raises UnsupportedTaxYearError if either
    figure has no schedule entry for tax_year. Never returns a negative
    withheld_amount or a benefit_after_withholding below 0.0."""
    exempt_figure = SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR if is_fra_attainment_year else SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA
    exempt_amount = exempt_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    rates = SS_EARNINGS_TEST_WITHHOLDING_RATIOS.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used = [exempt_figure.usage_for_year(tax_year), SS_EARNINGS_TEST_WITHHOLDING_RATIOS.usage_for_year(tax_year)]

    excess_earnings = max(0.0, earned_income - exempt_amount)
    ratio = rates.withholding_ratio_fra_year if is_fra_attainment_year else rates.withholding_ratio_below_fra
    withheld_amount = min(max(0.0, annual_benefit), excess_earnings * ratio)

    monthly_benefit = primary_insurance_amount / 12.0
    if withheld_amount > 0.0 and monthly_benefit > 0.0:
        # POMS RS 00615.482: a month with any withholding, even partial,
        # credits as one full deduction month -- hence ceil(), not a
        # dollar-prorated fraction of a month (research.md Decision 4).
        deduction_months_this_year = min(12, math.ceil(withheld_amount / monthly_benefit))
    else:
        deduction_months_this_year = 0

    return EarningsTestWithholdingResult(
        withheld_amount=withheld_amount,
        benefit_after_withholding=annual_benefit - withheld_amount,
        deduction_months_this_year=deduction_months_this_year,
        figures_used=figures_used,
    )


def compute_earnings_test_recredit(
    primary_insurance_amount: float,
    claiming_age: int,
    full_retirement_age: float,
    cumulative_months_withheld: int,
    tax_year: int,
) -> EarningsTestRecreditResult:
    """SSA's Adjustment of the Reduction Factor (ARF) at a member's
    FRA-attainment year (FR-006, FR-007): permanently reduces the
    early-claiming "months early" compute_social_security_benefit()
    originally applied for this member, by up to
    cumulative_months_withheld, capped so recredited_adjustment_factor
    never exceeds 1.0 -- ARF eliminates early-claiming reduction, it does
    not manufacture delayed-retirement credit past 100% of PIA
    (research.md Decision 4). Returns the member's unchanged original
    claiming-age-adjusted benefit when cumulative_months_withheld is 0.
    Raises UnsupportedTaxYearError if either earnings-test exempt-amount
    figure, or the claiming-age adjustment-rate figure, has no schedule
    entry for tax_year -- the exempt-amount figures are consulted purely
    for the citation trail (this function's own math needs neither
    dollar value), mirroring compute_survivor_benefit()'s own "consulted
    purely for the citation trail" precedent."""
    figures_used = [
        SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA.usage_for_year(tax_year),  # raises UnsupportedTaxYearError
        SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR.usage_for_year(tax_year),  # raises UnsupportedTaxYearError
    ]

    rates = SS_CLAIMING_AGE_ADJUSTMENT.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used.append(SS_CLAIMING_AGE_ADJUSTMENT.usage_for_year(tax_year))

    months_early_original = max(0.0, (full_retirement_age - claiming_age) * 12.0)
    months_recredited = min(float(cumulative_months_withheld), months_early_original)
    months_early_remaining = months_early_original - months_recredited

    tier_1_months = min(months_early_remaining, rates.early_reduction_tier_1_months)
    tier_2_months = max(0.0, months_early_remaining - rates.early_reduction_tier_1_months)
    reduction = tier_1_months * rates.early_reduction_rate_tier_1 + tier_2_months * rates.early_reduction_rate_tier_2
    recredited_adjustment_factor = 1.0 - reduction

    return EarningsTestRecreditResult(
        recredited_annual_benefit=primary_insurance_amount * recredited_adjustment_factor,
        recredited_adjustment_factor=recredited_adjustment_factor,
        # months_early_original can be fractional (full_retirement_age is a
        # float); when it caps months_recredited below the integer
        # cumulative_months_withheld, this truncates toward the whole
        # months actually consumed -- reporting only, the reduction itself
        # is computed from the continuous months_early_remaining above.
        months_recredited=int(months_recredited),
        figures_used=figures_used,
    )
