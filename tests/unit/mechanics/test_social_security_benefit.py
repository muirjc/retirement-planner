"""Unit tests for compute_social_security_benefit() (016-ss-claiming-age-
actuarial-adjustment, US1/US3), extended by compute_spousal_benefit_floor()
and compute_survivor_benefit() (017-ss-spousal-survivor-benefits, rp-52n).

SS_CLAIMING_AGE_ADJUSTMENT's rates (5/9 of 1%/month first 36 months early,
5/12 of 1%/month beyond, 2/3 of 1%/month delayed capped at age 70) are
cross-checked directly against 20 C.F.R. §404.410/§404.313's current text
(social_security_benefit.py's own module docstring); expected factors below
use those real figures, including the two textbook reference points most
commonly cited for Social Security claiming decisions (~70% of PIA at 62
against a 67 FRA, ~124% of PIA at 70 against a 67 FRA).

SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT's rates (25/36 of 1%/month first 36
months early, 5/12 of 1%/month beyond, no delayed credit) are likewise
cross-checked against 20 C.F.R. §404.410's wife's/husband's-benefit
paragraph -- a genuinely different tier-1 rate than the worker's-own-
benefit table above.
"""

import pytest

from retirement_planner.mechanics import (
    compute_earnings_test_recredit,
    compute_earnings_test_withholding,
    compute_social_security_benefit,
    compute_spousal_benefit_floor,
    compute_survivor_benefit,
)
from retirement_planner.tax import UnsupportedTaxYearError


def test_claiming_exactly_at_fra_pays_pia_unadjusted():
    result = compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=2026)
    assert result.annual_benefit == pytest.approx(30_000)
    assert result.adjustment_factor == pytest.approx(1.0)


def test_claiming_at_62_against_67_fra_is_about_70_percent_of_pia():
    result = compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026)
    # 60 months early: 36 * 5/9% + 24 * 5/12% = 20% + 10% = 30% reduction.
    assert result.adjustment_factor == pytest.approx(0.70)
    assert result.annual_benefit == pytest.approx(21_000)


def test_claiming_at_70_against_67_fra_is_about_124_percent_of_pia():
    result = compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=70, tax_year=2026)
    # 36 months delayed: 36 * 2/3% = 24% credit.
    assert result.adjustment_factor == pytest.approx(1.24)
    assert result.annual_benefit == pytest.approx(37_200)


def test_early_reduction_within_first_36_months_uses_only_tier_1_rate():
    # FRA 66, claiming at 64: 24 months early, all within the first-36 tier.
    result = compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=66.0, claiming_age=64, tax_year=2026)
    expected_reduction = 24 * (5 / 9) / 100
    assert result.adjustment_factor == pytest.approx(1.0 - expected_reduction)


def test_early_reduction_beyond_36_months_blends_both_tiers():
    # FRA 67, claiming at 62: 60 months early -- 36 at tier 1, 24 at tier 2.
    result = compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026)
    expected_reduction = 36 * (5 / 9) / 100 + 24 * (5 / 12) / 100
    assert result.adjustment_factor == pytest.approx(1.0 - expected_reduction)


def test_delayed_credit_stops_accruing_past_age_70():
    # A claiming_age above 70 (out of this tool's normal 62-70 range, but
    # the function itself does not enforce that bound -- validation.py
    # does) must not earn credit for the months past 70.
    at_70 = compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=70, tax_year=2026)
    past_70 = compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=71, tax_year=2026)
    assert past_70.adjustment_factor == pytest.approx(at_70.adjustment_factor)


def test_fractional_full_retirement_age_is_honored():
    # FRA 66 years 10 months (66.8333...), claiming at 67 -> ~2 months delayed.
    result = compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=66.0 + 10 / 12, claiming_age=67, tax_year=2026)
    expected_months_delayed = (67 - (66.0 + 10 / 12)) * 12
    expected_credit = expected_months_delayed * (2 / 3) / 100
    assert result.adjustment_factor == pytest.approx(1.0 + expected_credit)


def test_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=1999)


def test_figures_used_carries_the_claiming_age_adjustment_citation():
    result = compute_social_security_benefit(primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026)
    assert len(result.figures_used) == 1
    figure = result.figures_used[0]
    assert figure.name == "ss_claiming_age_adjustment_rates"
    assert "404.410" in figure.citation
    assert "404.313" in figure.citation
    assert figure.verified is True
    assert figure.last_verified is not None


# --- 017-ss-spousal-survivor-benefits: compute_spousal_benefit_floor() (rp-52n) ---


def test_spousal_amount_at_fra_is_exactly_half_of_other_pia():
    result = compute_spousal_benefit_floor(other_member_pia=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=2026)
    assert result.spousal_amount == pytest.approx(15_000)
    assert result.adjustment_factor == pytest.approx(1.0)


def test_spousal_early_reduction_within_first_36_months_uses_only_tier_1_rate():
    # FRA 67, claiming at 65: 24 months early, all within the first-36 tier.
    result = compute_spousal_benefit_floor(other_member_pia=30_000, full_retirement_age=67.0, claiming_age=65, tax_year=2026)
    expected_reduction = 24 * (25 / 36) / 100
    assert result.adjustment_factor == pytest.approx(1.0 - expected_reduction)
    assert result.spousal_amount == pytest.approx(15_000 * (1.0 - expected_reduction))


def test_spousal_early_reduction_beyond_36_months_blends_both_tiers():
    # FRA 67, claiming at 62: 60 months early -- 36 at tier 1 (25/36 of 1%),
    # 24 at tier 2 (5/12 of 1%) -- spec.md Acceptance Scenario 3.
    result = compute_spousal_benefit_floor(other_member_pia=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026)
    expected_reduction = 36 * (25 / 36) / 100 + 24 * (5 / 12) / 100
    assert expected_reduction == pytest.approx(0.35)  # 25% + 10%
    assert result.adjustment_factor == pytest.approx(0.65)
    assert result.spousal_amount == pytest.approx(9_750)


def test_spousal_amount_claimed_after_fra_still_capped_at_half_no_delayed_credit():
    # Unlike compute_social_security_benefit(), claiming after FRA earns no
    # delayed-retirement credit on a spousal amount -- it stays at exactly
    # 50% of the other member's PIA, never more.
    at_fra = compute_spousal_benefit_floor(other_member_pia=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=2026)
    after_fra = compute_spousal_benefit_floor(other_member_pia=30_000, full_retirement_age=67.0, claiming_age=70, tax_year=2026)
    assert after_fra.spousal_amount == pytest.approx(at_fra.spousal_amount)
    assert after_fra.adjustment_factor == pytest.approx(1.0)


def test_spousal_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_spousal_benefit_floor(other_member_pia=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=1999)


def test_spousal_figures_used_carries_the_spousal_adjustment_citation():
    result = compute_spousal_benefit_floor(other_member_pia=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026)
    assert len(result.figures_used) == 1
    figure = result.figures_used[0]
    assert figure.name == "ss_spousal_claiming_age_adjustment_rates"
    assert "404.410" in figure.citation
    assert figure.verified is True
    assert figure.last_verified is not None


# --- 017-ss-spousal-survivor-benefits: compute_survivor_benefit() (rp-52n) ---


def test_survivor_benefit_is_the_higher_of_the_two_amounts():
    result = compute_survivor_benefit(member_a_benefit=30_000, member_b_benefit=12_000, tax_year=2026)
    assert result.survivor_benefit == pytest.approx(30_000)


def test_survivor_benefit_is_symmetric_regardless_of_argument_order():
    """research.md Decision 4: the result does not depend on which member
    is passed first -- there is no "which member died" parameter, since
    the higher amount is the answer either way."""
    forward = compute_survivor_benefit(member_a_benefit=30_000, member_b_benefit=12_000, tax_year=2026)
    reversed_ = compute_survivor_benefit(member_a_benefit=12_000, member_b_benefit=30_000, tax_year=2026)
    assert forward.survivor_benefit == pytest.approx(reversed_.survivor_benefit)


def test_survivor_benefit_tie_returns_the_shared_value():
    result = compute_survivor_benefit(member_a_benefit=20_000, member_b_benefit=20_000, tax_year=2026)
    assert result.survivor_benefit == pytest.approx(20_000)


def test_survivor_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_survivor_benefit(member_a_benefit=30_000, member_b_benefit=12_000, tax_year=1999)


def test_survivor_figures_used_carries_the_survivor_benefit_rule_citation():
    result = compute_survivor_benefit(member_a_benefit=30_000, member_b_benefit=12_000, tax_year=2026)
    assert len(result.figures_used) == 1
    figure = result.figures_used[0]
    assert figure.name == "ss_survivor_benefit_rule"
    assert "402(e)" in figure.citation or "402(f)" in figure.citation
    assert figure.verified is True
    assert figure.last_verified is not None


# --- 025-ss-earnings-test (rp-acq) --------------------------------------
#
# 2026 SSA-published exempt amounts (module docstring / SourcedFigure
# citations): $24,480/yr below FRA, $65,160/yr in the FRA-attainment year.


def test_earnings_below_fra_threshold_withholds_one_dollar_per_two_over():
    result = compute_earnings_test_withholding(
        annual_benefit=20_000,
        primary_insurance_amount=20_000,
        earned_income=60_000,
        is_fra_attainment_year=False,
        tax_year=2026,
    )
    assert result.withheld_amount == pytest.approx((60_000 - 24_480) / 2)
    assert result.benefit_after_withholding == pytest.approx(20_000 - result.withheld_amount)


def test_earnings_at_or_below_below_fra_threshold_withholds_nothing():
    result = compute_earnings_test_withholding(
        annual_benefit=20_000,
        primary_insurance_amount=20_000,
        earned_income=24_480,
        is_fra_attainment_year=False,
        tax_year=2026,
    )
    assert result.withheld_amount == pytest.approx(0.0)
    assert result.benefit_after_withholding == pytest.approx(20_000)
    assert result.deduction_months_this_year == 0


def test_fra_attainment_year_withholds_one_dollar_per_three_over_higher_threshold():
    result = compute_earnings_test_withholding(
        annual_benefit=20_000,
        primary_insurance_amount=20_000,
        earned_income=70_000,
        is_fra_attainment_year=True,
        tax_year=2026,
    )
    assert result.withheld_amount == pytest.approx((70_000 - 65_160) / 3)


def test_fra_attainment_year_earnings_below_below_fra_threshold_would_have_withheld_but_dont():
    # Earnings between the FRA-year threshold's lower bound (65,160) is not
    # tested here; instead confirm the FRA-year rule -- not the stricter
    # below-FRA rule -- is actually what's applied for a value that WOULD
    # trigger withholding under the below-FRA rule but not the FRA-year one.
    result = compute_earnings_test_withholding(
        annual_benefit=20_000,
        primary_insurance_amount=20_000,
        earned_income=30_000,
        is_fra_attainment_year=True,
        tax_year=2026,
    )
    assert result.withheld_amount == pytest.approx(0.0)


def test_withholding_never_drives_benefit_below_zero():
    result = compute_earnings_test_withholding(
        annual_benefit=5_000,
        primary_insurance_amount=20_000,
        earned_income=500_000,
        is_fra_attainment_year=False,
        tax_year=2026,
    )
    assert result.withheld_amount == pytest.approx(5_000)
    assert result.benefit_after_withholding == pytest.approx(0.0)


def test_partial_month_withholding_still_credits_one_full_deduction_month():
    # Monthly benefit is 20,000/12 ~= 1,666.67; a withheld amount smaller
    # than one full month's benefit still credits a whole month (POMS RS
    # 00615.482 -- proration has no effect on ARF crediting).
    result = compute_earnings_test_withholding(
        annual_benefit=20_000,
        primary_insurance_amount=20_000,
        earned_income=24_680,  # $200 over the below-FRA threshold -> $100 withheld
        is_fra_attainment_year=False,
        tax_year=2026,
    )
    assert result.withheld_amount == pytest.approx(100.0)
    assert result.deduction_months_this_year == 1


def test_deduction_months_this_year_caps_at_twelve():
    result = compute_earnings_test_withholding(
        annual_benefit=1_000_000,
        primary_insurance_amount=12_000,  # $1,000/mo
        earned_income=10_000_000,
        is_fra_attainment_year=False,
        tax_year=2026,
    )
    assert result.deduction_months_this_year == 12


def test_earnings_test_withholding_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_earnings_test_withholding(
            annual_benefit=20_000,
            primary_insurance_amount=20_000,
            earned_income=60_000,
            is_fra_attainment_year=False,
            tax_year=1999,
        )


def test_earnings_test_withholding_figures_used_carries_both_citations():
    result = compute_earnings_test_withholding(
        annual_benefit=20_000,
        primary_insurance_amount=20_000,
        earned_income=60_000,
        is_fra_attainment_year=False,
        tax_year=2026,
    )
    names = {figure.name for figure in result.figures_used}
    assert names == {"ss_earnings_test_exempt_amount_below_fra", "ss_earnings_test_withholding_ratios"}
    assert all(figure.verified is True for figure in result.figures_used)


def test_recredit_with_no_prior_withholding_leaves_benefit_unchanged():
    result = compute_earnings_test_recredit(
        primary_insurance_amount=30_000,
        claiming_age=62,
        full_retirement_age=67.0,
        cumulative_months_withheld=0,
        tax_year=2026,
    )
    assert result.recredited_adjustment_factor == pytest.approx(0.70)  # unchanged 62-vs-67 reduction
    assert result.recredited_annual_benefit == pytest.approx(21_000)
    assert result.months_recredited == 0


def test_recredit_partially_restores_the_early_claiming_reduction():
    result = compute_earnings_test_recredit(
        primary_insurance_amount=20_000,
        claiming_age=62,
        full_retirement_age=67.0,
        cumulative_months_withheld=24,
        tax_year=2026,
    )
    # 60 months early originally, 24 credited back -> 36 remaining, all
    # within tier 1: 36 * 5/9% = 20% reduction -> 0.80 factor.
    assert result.recredited_adjustment_factor == pytest.approx(0.80)
    assert result.recredited_annual_benefit == pytest.approx(16_000)
    assert result.months_recredited == 24


def test_recredit_never_exceeds_full_pia_even_with_excess_withheld_months():
    result = compute_earnings_test_recredit(
        primary_insurance_amount=20_000,
        claiming_age=62,
        full_retirement_age=67.0,
        cumulative_months_withheld=600,  # far more than the 60 months originally reduced
        tax_year=2026,
    )
    assert result.recredited_adjustment_factor == pytest.approx(1.0)
    assert result.recredited_annual_benefit == pytest.approx(20_000)


def test_earnings_test_recredit_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_earnings_test_recredit(
            primary_insurance_amount=20_000,
            claiming_age=62,
            full_retirement_age=67.0,
            cumulative_months_withheld=24,
            tax_year=1999,
        )
