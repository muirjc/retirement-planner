"""Unit tests for compute_hsa_eligibility() and compute_hsa_contribution()
(010-advanced-tax-benefits, US3).

Expected limits are hand-calculated against this feature's own
placeholder HSA contribution-limit figures (hsa.py) -- see that module's
docstring for why the dollar amounts are illustrative pending citation
verification against the IRS's annual Rev. Proc. HSA-limits announcement
(research.md §7).
"""

import pytest

from retirement_planner.mechanics import HsaEligibility
from retirement_planner.mechanics.hsa import compute_hsa_contribution, compute_hsa_eligibility
from retirement_planner.tax import UnsupportedTaxYearError


def test_hdhp_covered_non_medicare_member_is_eligible():
    result = compute_hsa_eligibility(
        members=[("you", 60, True)], medicare_enrolled={"you": False},
    )
    assert result == [HsaEligibility(person_name="you", age=60, eligible=True, reason=None)]


def test_member_without_hdhp_coverage_is_not_eligible():
    result = compute_hsa_eligibility(
        members=[("you", 60, False)], medicare_enrolled={"you": False},
    )
    assert result[0].eligible is False
    assert result[0].reason is not None


def test_medicare_enrolled_member_is_not_eligible_regardless_of_hdhp_coverage():
    """FR-009."""
    result = compute_hsa_eligibility(
        members=[("you", 66, True)], medicare_enrolled={"you": True},
    )
    assert result[0].eligible is False
    assert "medicare" in result[0].reason.lower()


def test_one_members_eligibility_is_independent_of_anothers():
    """FR-010: a younger spouse's eligibility is unaffected by the older
    member's Medicare enrollment."""
    result = compute_hsa_eligibility(
        members=[("you", 66, True), ("spouse", 60, True)],
        medicare_enrolled={"you": True, "spouse": False},
    )
    by_name = {e.person_name: e for e in result}
    assert by_name["you"].eligible is False
    assert by_name["spouse"].eligible is True


def test_one_eligible_member_uses_the_self_only_limit():
    eligibility = compute_hsa_eligibility(members=[("you", 45, True)], medicare_enrolled={"you": False})
    result = compute_hsa_contribution(eligibility, configured_annual_amount=3_000.0, tax_year=2026)
    assert result.applicable_limit == 4_300.0
    assert result.amount_contributed == 3_000.0
    assert result.rejected_reason is None


def test_two_eligible_members_use_the_family_limit():
    eligibility = compute_hsa_eligibility(
        members=[("you", 45, True), ("spouse", 43, True)], medicare_enrolled={"you": False, "spouse": False},
    )
    result = compute_hsa_contribution(eligibility, configured_annual_amount=8_000.0, tax_year=2026)
    assert result.applicable_limit == 8_550.0
    assert result.amount_contributed == 8_000.0


def test_catchup_added_once_per_eligible_member_55_or_older():
    eligibility = compute_hsa_eligibility(
        members=[("you", 56, True), ("spouse", 57, True)], medicare_enrolled={"you": False, "spouse": False},
    )
    result = compute_hsa_contribution(eligibility, configured_annual_amount=20_000.0, tax_year=2026)
    assert result.applicable_limit == 8_550.0 + 1_000.0 * 2


def test_configured_amount_above_the_limit_is_capped_and_flagged():
    eligibility = compute_hsa_eligibility(members=[("you", 45, True)], medicare_enrolled={"you": False})
    result = compute_hsa_contribution(eligibility, configured_annual_amount=10_000.0, tax_year=2026)
    assert result.amount_contributed == 4_300.0
    assert result.rejected_reason is not None


def test_no_eligible_member_means_zero_contribution_not_an_exception():
    """FR-012, research.md §5 -- never raises for the ordinary "not
    eligible this year" case."""
    eligibility = compute_hsa_eligibility(members=[("you", 66, True)], medicare_enrolled={"you": True})
    result = compute_hsa_contribution(eligibility, configured_annual_amount=5_000.0, tax_year=2026)
    assert result.amount_contributed == 0.0
    assert result.rejected_reason is not None
    assert result.applicable_limit == 0.0


def test_figures_used_reflects_the_limit_table_verification_status():
    eligibility = compute_hsa_eligibility(members=[("you", 45, True)], medicare_enrolled={"you": False})
    result = compute_hsa_contribution(eligibility, configured_annual_amount=1_000.0, tax_year=2026)
    assert len(result.figures_used) == 1
    assert result.figures_used[0].verified is False


def test_unsupported_tax_year_raises():
    eligibility = compute_hsa_eligibility(members=[("you", 45, True)], medicare_enrolled={"you": False})
    with pytest.raises(UnsupportedTaxYearError):
        compute_hsa_contribution(eligibility, configured_annual_amount=1_000.0, tax_year=1999)
