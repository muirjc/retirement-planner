"""Unit tests for compute_social_security_benefit() (016-ss-claiming-age-
actuarial-adjustment, US1/US3).

SS_CLAIMING_AGE_ADJUSTMENT's rates (5/9 of 1%/month first 36 months early,
5/12 of 1%/month beyond, 2/3 of 1%/month delayed capped at age 70) are
cross-checked directly against 20 C.F.R. §404.410/§404.313's current text
(social_security_benefit.py's own module docstring); expected factors below
use those real figures, including the two textbook reference points most
commonly cited for Social Security claiming decisions (~70% of PIA at 62
against a 67 FRA, ~124% of PIA at 70 against a 67 FRA).
"""

import pytest

from retirement_planner.mechanics import compute_social_security_benefit
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
