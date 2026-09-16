"""Unit tests for compute_401k_eligibility() and compute_401k_contribution()
(rp-wei, Phase 1 -- rp-wei.1).

The elective-deferral limit figures in contribution_401k.py are a
PLACEHOLDER (verified=False), not yet cross-checked against a real IRS
Revenue Procedure -- these tests pin the module's own current placeholder
values ($24,500 elective deferral, $8,000 catch-up at 50+), not a
verified real-world figure. A future figure-verification pass should
update both the module and these tests together.
"""

import pytest

from retirement_planner.mechanics import Contribution401kEligibility
from retirement_planner.mechanics.contribution_401k import compute_401k_contribution, compute_401k_eligibility
from retirement_planner.tax import UnsupportedTaxYearError


def test_member_with_earned_income_is_eligible():
    result = compute_401k_eligibility(members=[("you", 45, 150_000.0)])
    assert result == [
        Contribution401kEligibility(
            person_name="you", age=45, earned_income_this_year=150_000.0, eligible=True, reason=None
        )
    ]


def test_member_with_zero_earned_income_is_not_eligible():
    result = compute_401k_eligibility(members=[("you", 45, 0.0)])
    assert result[0].eligible is False
    assert result[0].reason is not None


def test_one_members_eligibility_is_independent_of_anothers():
    result = compute_401k_eligibility(members=[("you", 45, 150_000.0), ("spouse", 43, 0.0)])
    by_name = {e.person_name: e for e in result}
    assert by_name["you"].eligible is True
    assert by_name["spouse"].eligible is False


def test_under_50_member_uses_the_base_limit_with_no_catchup():
    eligibility = compute_401k_eligibility(members=[("you", 45, 150_000.0)])
    result = compute_401k_contribution(
        eligibility, configured_amounts={"you": (20_000.0, 0.0)}, tax_year=2026
    )
    assert result.member_results[0].applicable_limit == 24_500.0
    assert result.member_results[0].pretax_contributed == 20_000.0
    assert result.member_results[0].rejected_reason is None


def test_catchup_added_once_for_a_50_or_older_member():
    eligibility = compute_401k_eligibility(members=[("you", 50, 150_000.0)])
    result = compute_401k_contribution(
        eligibility, configured_amounts={"you": (30_000.0, 0.0)}, tax_year=2026
    )
    assert result.member_results[0].applicable_limit == 24_500.0 + 8_000.0


def test_limit_is_per_person_not_household_pooled():
    """Unlike HSA's household-pooled self-only/family tiers, each member
    gets their own full limit -- two eligible members don't share or
    split one household figure."""
    eligibility = compute_401k_eligibility(members=[("you", 45, 150_000.0), ("spouse", 43, 150_000.0)])
    result = compute_401k_contribution(
        eligibility, configured_amounts={"you": (24_500.0, 0.0), "spouse": (24_500.0, 0.0)}, tax_year=2026
    )
    by_name = {r.person_name: r for r in result.member_results}
    assert by_name["you"].applicable_limit == 24_500.0
    assert by_name["spouse"].applicable_limit == 24_500.0
    assert result.total_pretax_contributed == 49_000.0


def test_configured_total_above_the_limit_is_capped_pretax_first():
    """When combined pretax+Roth exceeds the limit, pretax is capped
    first and Roth fills whatever headroom remains."""
    eligibility = compute_401k_eligibility(members=[("you", 45, 150_000.0)])
    result = compute_401k_contribution(
        eligibility, configured_amounts={"you": (20_000.0, 10_000.0)}, tax_year=2026
    )
    member = result.member_results[0]
    assert member.pretax_contributed == 20_000.0
    assert member.roth_contributed == pytest.approx(4_500.0)
    assert member.pretax_contributed + member.roth_contributed == pytest.approx(24_500.0)
    assert member.rejected_reason is not None


def test_pretax_alone_above_the_limit_is_capped_and_roth_gets_nothing():
    eligibility = compute_401k_eligibility(members=[("you", 45, 150_000.0)])
    result = compute_401k_contribution(
        eligibility, configured_amounts={"you": (30_000.0, 5_000.0)}, tax_year=2026
    )
    member = result.member_results[0]
    assert member.pretax_contributed == 24_500.0
    assert member.roth_contributed == 0.0


def test_configured_amount_capped_at_earned_income_when_lower_than_the_irs_limit():
    """A member can't defer more than they actually earned this year,
    even if the IRS limit is higher."""
    eligibility = compute_401k_eligibility(members=[("you", 45, 10_000.0)])
    result = compute_401k_contribution(
        eligibility, configured_amounts={"you": (15_000.0, 0.0)}, tax_year=2026
    )
    member = result.member_results[0]
    assert member.pretax_contributed == 10_000.0
    assert member.rejected_reason is not None


def test_ineligible_member_contributes_nothing_regardless_of_configured_amount():
    """Never raises for the ordinary "not eligible this year" case."""
    eligibility = compute_401k_eligibility(members=[("you", 45, 0.0)])
    result = compute_401k_contribution(
        eligibility, configured_amounts={"you": (20_000.0, 5_000.0)}, tax_year=2026
    )
    member = result.member_results[0]
    assert member.eligible is False
    assert member.pretax_contributed == 0.0
    assert member.roth_contributed == 0.0
    assert member.rejected_reason is not None
    assert result.total_pretax_contributed == 0.0
    assert result.total_roth_contributed == 0.0


def test_unconfigured_member_present_in_eligibility_contributes_nothing():
    """A member with no entry in configured_amounts (no contribution_401k
    block configured) contributes 0.0, never a KeyError."""
    eligibility = compute_401k_eligibility(members=[("you", 45, 150_000.0)])
    result = compute_401k_contribution(eligibility, configured_amounts={}, tax_year=2026)
    member = result.member_results[0]
    assert member.pretax_contributed == 0.0
    assert member.roth_contributed == 0.0
    assert member.rejected_reason is None


def test_nothing_configured_household_wide_never_consults_the_limit_figure():
    """The unverified placeholder limit must never be reported as "used"
    for a household that hasn't configured any 401(k) contribution at
    all -- otherwise every such scenario (the overwhelming majority)
    would show an unverified figure in reporting it never actually
    needed, breaking this feature's default-preserving requirement."""
    eligibility = compute_401k_eligibility(members=[("you", 45, 150_000.0), ("spouse", 43, 0.0)])
    result = compute_401k_contribution(
        eligibility, configured_amounts={"you": (0.0, 0.0), "spouse": (0.0, 0.0)}, tax_year=2026
    )
    assert result.figures_used == []
    assert result.total_pretax_contributed == 0.0
    assert result.total_roth_contributed == 0.0


def test_nothing_configured_never_raises_even_for_an_undocumented_tax_year():
    """The limit lookup (and therefore UnsupportedTaxYearError) is
    entirely skipped when nothing is configured -- a household not using
    this feature at all must never be affected by an out-of-range
    tax_year this feature's own limit table doesn't document."""
    eligibility = compute_401k_eligibility(members=[("you", 45, 150_000.0)])
    result = compute_401k_contribution(eligibility, configured_amounts={}, tax_year=1999)
    assert result.figures_used == []


def test_figures_used_reflects_the_limit_table_unverified_status():
    eligibility = compute_401k_eligibility(members=[("you", 45, 150_000.0)])
    result = compute_401k_contribution(
        eligibility, configured_amounts={"you": (1_000.0, 0.0)}, tax_year=2026
    )
    assert len(result.figures_used) == 1
    assert result.figures_used[0].verified is False
    assert "402(g)" in result.figures_used[0].citation


def test_unsupported_tax_year_raises():
    eligibility = compute_401k_eligibility(members=[("you", 45, 150_000.0)])
    with pytest.raises(UnsupportedTaxYearError):
        compute_401k_contribution(eligibility, configured_amounts={"you": (1_000.0, 0.0)}, tax_year=1999)
