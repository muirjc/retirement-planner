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
    compute_social_security_benefit,
    compute_spousal_benefit_floor,
    compute_survivor_benefit,
)
from retirement_planner.tax import UnsupportedTaxYearError


def test_claiming_exactly_at_fra_pays_pia_unadjusted():
    result = compute_social_security_benefit(
        primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=2026
    )
    assert result.annual_benefit == pytest.approx(30_000)
    assert result.adjustment_factor == pytest.approx(1.0)


def test_claiming_at_62_against_67_fra_is_about_70_percent_of_pia():
    result = compute_social_security_benefit(
        primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026
    )
    # 60 months early: 36 * 5/9% + 24 * 5/12% = 20% + 10% = 30% reduction.
    assert result.adjustment_factor == pytest.approx(0.70)
    assert result.annual_benefit == pytest.approx(21_000)


def test_claiming_at_70_against_67_fra_is_about_124_percent_of_pia():
    result = compute_social_security_benefit(
        primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=70, tax_year=2026
    )
    # 36 months delayed: 36 * 2/3% = 24% credit.
    assert result.adjustment_factor == pytest.approx(1.24)
    assert result.annual_benefit == pytest.approx(37_200)


def test_early_reduction_within_first_36_months_uses_only_tier_1_rate():
    # FRA 66, claiming at 64: 24 months early, all within the first-36 tier.
    result = compute_social_security_benefit(
        primary_insurance_amount=30_000, full_retirement_age=66.0, claiming_age=64, tax_year=2026
    )
    expected_reduction = 24 * (5 / 9) / 100
    assert result.adjustment_factor == pytest.approx(1.0 - expected_reduction)


def test_early_reduction_beyond_36_months_blends_both_tiers():
    # FRA 67, claiming at 62: 60 months early -- 36 at tier 1, 24 at tier 2.
    result = compute_social_security_benefit(
        primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026
    )
    expected_reduction = 36 * (5 / 9) / 100 + 24 * (5 / 12) / 100
    assert result.adjustment_factor == pytest.approx(1.0 - expected_reduction)


def test_delayed_credit_stops_accruing_past_age_70():
    # A claiming_age above 70 (out of this tool's normal 62-70 range, but
    # the function itself does not enforce that bound -- validation.py
    # does) must not earn credit for the months past 70.
    at_70 = compute_social_security_benefit(
        primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=70, tax_year=2026
    )
    past_70 = compute_social_security_benefit(
        primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=71, tax_year=2026
    )
    assert past_70.adjustment_factor == pytest.approx(at_70.adjustment_factor)


def test_fractional_full_retirement_age_is_honored():
    # FRA 66 years 10 months (66.8333...), claiming at 67 -> ~2 months delayed.
    result = compute_social_security_benefit(
        primary_insurance_amount=30_000, full_retirement_age=66.0 + 10 / 12, claiming_age=67, tax_year=2026
    )
    expected_months_delayed = (67 - (66.0 + 10 / 12)) * 12
    expected_credit = expected_months_delayed * (2 / 3) / 100
    assert result.adjustment_factor == pytest.approx(1.0 + expected_credit)


def test_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_social_security_benefit(
            primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=1999
        )


def test_figures_used_carries_the_claiming_age_adjustment_citation():
    result = compute_social_security_benefit(
        primary_insurance_amount=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026
    )
    assert len(result.figures_used) == 1
    figure = result.figures_used[0]
    assert figure.name == "ss_claiming_age_adjustment_rates"
    assert "404.410" in figure.citation
    assert "404.313" in figure.citation
    assert figure.verified is True
    assert figure.last_verified is not None


# --- 017-ss-spousal-survivor-benefits: compute_spousal_benefit_floor() (rp-52n) ---


def test_spousal_amount_at_fra_is_exactly_half_of_other_pia():
    result = compute_spousal_benefit_floor(
        other_member_pia=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=2026
    )
    assert result.spousal_amount == pytest.approx(15_000)
    assert result.adjustment_factor == pytest.approx(1.0)


def test_spousal_early_reduction_within_first_36_months_uses_only_tier_1_rate():
    # FRA 67, claiming at 65: 24 months early, all within the first-36 tier.
    result = compute_spousal_benefit_floor(
        other_member_pia=30_000, full_retirement_age=67.0, claiming_age=65, tax_year=2026
    )
    expected_reduction = 24 * (25 / 36) / 100
    assert result.adjustment_factor == pytest.approx(1.0 - expected_reduction)
    assert result.spousal_amount == pytest.approx(15_000 * (1.0 - expected_reduction))


def test_spousal_early_reduction_beyond_36_months_blends_both_tiers():
    # FRA 67, claiming at 62: 60 months early -- 36 at tier 1 (25/36 of 1%),
    # 24 at tier 2 (5/12 of 1%) -- spec.md Acceptance Scenario 3.
    result = compute_spousal_benefit_floor(
        other_member_pia=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026
    )
    expected_reduction = 36 * (25 / 36) / 100 + 24 * (5 / 12) / 100
    assert expected_reduction == pytest.approx(0.35)  # 25% + 10%
    assert result.adjustment_factor == pytest.approx(0.65)
    assert result.spousal_amount == pytest.approx(9_750)


def test_spousal_amount_claimed_after_fra_still_capped_at_half_no_delayed_credit():
    # Unlike compute_social_security_benefit(), claiming after FRA earns no
    # delayed-retirement credit on a spousal amount -- it stays at exactly
    # 50% of the other member's PIA, never more.
    at_fra = compute_spousal_benefit_floor(
        other_member_pia=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=2026
    )
    after_fra = compute_spousal_benefit_floor(
        other_member_pia=30_000, full_retirement_age=67.0, claiming_age=70, tax_year=2026
    )
    assert after_fra.spousal_amount == pytest.approx(at_fra.spousal_amount)
    assert after_fra.adjustment_factor == pytest.approx(1.0)


def test_spousal_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_spousal_benefit_floor(
            other_member_pia=30_000, full_retirement_age=67.0, claiming_age=67, tax_year=1999
        )


def test_spousal_figures_used_carries_the_spousal_adjustment_citation():
    result = compute_spousal_benefit_floor(
        other_member_pia=30_000, full_retirement_age=67.0, claiming_age=62, tax_year=2026
    )
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
