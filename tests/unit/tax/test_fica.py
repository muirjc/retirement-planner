"""Unit tests for compute_fica_tax() (022-fica-payroll-tax, rp-elp).

Expected amounts are hand-calculated against fica.py's own cited figures
(6.2% OASDI up to a $184,500 wage base, 1.45% uncapped Medicare, 0.9%
Additional Medicare Tax above a filing-status threshold) -- see
fica.py's own module docstring and specs/022-fica-payroll-tax/research.md
§4 for the citations.
"""

import pytest

from retirement_planner.tax import UnsupportedTaxYearError
from retirement_planner.tax.fica import compute_fica_tax


def test_earned_income_under_wage_base_pays_regular_rates_only():
    """spec.md Acceptance Scenario US1.1."""
    result = compute_fica_tax({"Alex": 40_000.0}, "single", 2026)
    assert result.member_oasdi_tax["Alex"] == pytest.approx(40_000 * 0.062)
    assert result.member_medicare_tax["Alex"] == pytest.approx(40_000 * 0.0145)
    assert result.additional_medicare_tax == 0.0
    assert result.total_fica_tax == pytest.approx(40_000 * 0.062 + 40_000 * 0.0145)


def test_earned_income_over_wage_base_caps_oasdi_not_medicare():
    """spec.md Acceptance Scenario US2.1: OASDI caps at the wage base,
    Medicare keeps scaling with the full amount."""
    result = compute_fica_tax({"Alex": 250_000.0}, "single", 2026)
    assert result.member_oasdi_tax["Alex"] == pytest.approx(184_500 * 0.062)
    assert result.member_medicare_tax["Alex"] == pytest.approx(250_000 * 0.0145)


def test_additional_medicare_tax_applies_above_single_threshold():
    """spec.md Acceptance Scenario US3.1."""
    result = compute_fica_tax({"Alex": 250_000.0}, "single", 2026)
    assert result.additional_medicare_tax == pytest.approx((250_000 - 200_000) * 0.009)


def test_additional_medicare_tax_applies_to_combined_mfj_earnings_even_when_neither_spouse_alone_exceeds_it():
    """spec.md Acceptance Scenario US3.2 / Edge Cases: each spouse
    individually earns $150k (under the $200k single-shaped amount), but
    combined ($300k) exceeds the $250k MFJ threshold -- computed once for
    the household, not doubled or skipped."""
    result = compute_fica_tax({"Alex": 150_000.0, "Sam": 150_000.0}, "married_filing_jointly", 2026)
    assert result.additional_medicare_tax == pytest.approx((300_000 - 250_000) * 0.009)


def test_additional_medicare_tax_is_zero_at_or_below_threshold():
    result = compute_fica_tax({"Alex": 200_000.0}, "single", 2026)
    assert result.additional_medicare_tax == 0.0


def test_oasdi_wage_base_applies_per_member_not_pooled():
    """spec.md Edge Cases: the wage-base cap is per-worker -- two members
    each under the cap individually are each capped independently, never
    pooled into one shared cap."""
    result = compute_fica_tax({"Alex": 150_000.0, "Sam": 150_000.0}, "married_filing_jointly", 2026)
    assert result.member_oasdi_tax["Alex"] == pytest.approx(150_000 * 0.062)
    assert result.member_oasdi_tax["Sam"] == pytest.approx(150_000 * 0.062)


def test_pension_or_annuity_income_never_enters_this_calculation():
    """spec.md FR-001/FR-002 -- compute_fica_tax() has no notion of
    pension/annuity at all; a caller that (incorrectly) passed such
    income in would be taxed on it, since this module trusts its input
    entirely (module docstring's "caller determines the base" precedent).
    This test documents that the exclusion is the *caller's*
    responsibility (comparison.projection._member_earned_income_amounts()),
    not this function's."""
    only_earned = compute_fica_tax({"Alex": 40_000.0}, "single", 2026)
    assert only_earned.total_fica_tax > 0.0


def test_no_members_has_zero_tax_but_figures_used_still_populated():
    """mirrors compute_early_withdrawal_penalty()'s own "always cited,
    even at zero" precedent."""
    result = compute_fica_tax({}, "single", 2026)
    assert result.total_fica_tax == 0.0
    assert result.member_oasdi_tax == {}
    assert result.member_medicare_tax == {}
    assert len(result.figures_used) == 5


def test_zero_earned_income_member_has_zero_tax():
    result = compute_fica_tax({"Alex": 0.0}, "single", 2026)
    assert result.member_oasdi_tax["Alex"] == 0.0
    assert result.member_medicare_tax["Alex"] == 0.0
    assert result.total_fica_tax == 0.0


def test_figures_used_carries_expected_citations_and_verified_flags():
    result = compute_fica_tax({"Alex": 40_000.0}, "single", 2026)
    names = {usage.name for usage in result.figures_used}
    assert names == {
        "fica_oasdi_rate",
        "fica_oasdi_wage_base",
        "fica_medicare_rate",
        "additional_medicare_tax_rate",
        "additional_medicare_tax_threshold_single",
    }
    assert all(usage.verified is True for usage in result.figures_used)
    assert all(usage.last_verified is not None for usage in result.figures_used)


def test_mfj_threshold_figure_used_differs_from_single():
    result = compute_fica_tax({"Alex": 40_000.0}, "married_filing_jointly", 2026)
    names = {usage.name for usage in result.figures_used}
    assert "additional_medicare_tax_threshold_mfj" in names
    assert "additional_medicare_tax_threshold_single" not in names


def test_rates_and_wage_base_are_fixed_across_documented_years():
    """Mirrors compute_early_withdrawal_penalty()'s own fixed-rate test --
    this engine's real-dollar, no-further-indexing convention (research.md
    §4) holds these flat across every documented year."""
    for tax_year in (2020, 2026, 2050, 2074):
        result = compute_fica_tax({"Alex": 40_000.0}, "single", tax_year)
        assert result.total_fica_tax == pytest.approx(40_000 * 0.062 + 40_000 * 0.0145)


def test_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_fica_tax({"Alex": 40_000.0}, "single", 1999)
