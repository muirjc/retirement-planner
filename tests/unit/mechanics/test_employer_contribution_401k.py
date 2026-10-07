"""Unit tests for compute_employer_contribution() (rp-04u, Phase 1 --
rp-04u.1).

The §415(c) total-additions limit figure in employer_contribution_401k.py
is a PLACEHOLDER (verified=False, $72,000), not yet cross-checked against
a real IRS Revenue Procedure -- mirrors contribution_401k.py's own
unverified §402(g) figure. These tests pin the module's own current
placeholder value, not a verified real-world figure. A future
figure-verification pass should update both the module and these tests
together.
"""

import pytest

from retirement_planner.mechanics import Contribution401kMemberResult
from retirement_planner.mechanics.employer_contribution_401k import compute_employer_contribution
from retirement_planner.tax import UnsupportedTaxYearError


def _employee_result(person_name="you", pretax=0.0, roth=0.0, age=45, eligible=True):
    return Contribution401kMemberResult(
        person_name=person_name,
        age=age,
        eligible=eligible,
        applicable_limit=24_500.0,
        pretax_contributed=pretax,
        roth_contributed=roth,
        rejected_reason=None,
    )


def test_match_formula_applies_rate_to_capped_employee_contribution():
    """50% match, capped at 6% of $150,000 pay ($9,000) -- employee
    contributed $20,000, so only $9,000 of it is eligible for matching."""
    employee = [_employee_result(pretax=20_000.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (0.5, 0.06, 0.0)},
        member_earned_income={"you": 150_000.0},
        tax_year=2026,
    )
    member = result.member_results[0]
    assert member.matched_contribution == 9_000.0
    assert member.match_amount == 4_500.0
    assert result.total_match == 4_500.0


def test_pay_cap_limits_the_matched_base_even_with_small_contribution():
    """The pay cap, not the employee's own contribution, is the binding
    constraint when the employee contributed more than the cap allows."""
    employee = [_employee_result(pretax=5_000.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (1.0, 0.02, 0.0)},  # 100% match, capped at 2% of pay
        member_earned_income={"you": 100_000.0},  # 2% of pay = $2,000
        tax_year=2026,
    )
    member = result.member_results[0]
    assert member.matched_contribution == 2_000.0
    assert member.match_amount == 2_000.0


def test_lump_sum_only_configuration_ignores_employee_contribution_entirely():
    """A lump sum with no match formula (match_rate=0) is independent of
    what the employee themselves deferred -- even a member with zero
    employee contribution gets the full lump sum."""
    employee = [_employee_result(pretax=0.0, roth=0.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (0.0, 0.0, 2_000.0)},
        member_earned_income={"you": 150_000.0},
        tax_year=2026,
    )
    member = result.member_results[0]
    assert member.match_amount == 0.0
    assert member.lump_sum_amount == 2_000.0
    assert result.total_lump_sum == 2_000.0


def test_match_only_configuration_has_no_lump_sum():
    employee = [_employee_result(pretax=10_000.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (0.5, 0.06, 0.0)},
        member_earned_income={"you": 150_000.0},
        tax_year=2026,
    )
    member = result.member_results[0]
    assert member.match_amount > 0.0
    assert member.lump_sum_amount == 0.0


def test_match_and_lump_sum_together():
    employee = [_employee_result(pretax=20_000.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (0.5, 0.06, 2_000.0)},
        member_earned_income={"you": 150_000.0},
        tax_year=2026,
    )
    member = result.member_results[0]
    assert member.match_amount == 4_500.0
    assert member.lump_sum_amount == 2_000.0
    assert result.total_match == 4_500.0
    assert result.total_lump_sum == 2_000.0


def test_415c_cap_trims_lump_sum_first_leaving_match_untouched():
    """lump sum is large enough to absorb the entire excess on its own --
    match stays exactly as the formula computed it."""
    employee = [_employee_result(pretax=24_500.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (1.0, 1.0, 30_000.0)},  # 100% match, no effective pay cap
        member_earned_income={"you": 200_000.0},
        tax_year=2026,
    )
    member = result.member_results[0]
    # employee 24,500 + match 24,500 + lump 30,000 = 79,000 > 72,000 limit;
    # excess 7,000 comes entirely out of lump sum.
    assert member.match_amount == pytest.approx(24_500.0)
    assert member.lump_sum_amount == pytest.approx(23_000.0)
    assert member.rejected_reason is not None
    assert "415(c)" in member.rejected_reason


def test_415c_cap_trims_match_once_lump_sum_is_exhausted():
    """When the excess is larger than the lump sum alone, lump sum is
    zeroed out first and the remainder comes out of match -- the
    employee's own already-§402(g)-capped contribution is never touched."""
    employee = [_employee_result(pretax=24_500.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (2.0, 1.0, 5_000.0)},
        member_earned_income={"you": 200_000.0},
        tax_year=2026,
    )
    member = result.member_results[0]
    # employee 24,500 + match 49,000 + lump 5,000 = 78,500 > 72,000;
    # excess 6,500 -- lump sum (5,000) zeroed, remaining 1,500 trimmed
    # from match (49,000 -> 47,500).
    assert member.lump_sum_amount == 0.0
    assert member.match_amount == pytest.approx(47_500.0)


def test_415c_cap_never_reduces_the_employees_own_contribution():
    """Confirms the employee's own Contribution401kMemberResult is passed
    through unmodified -- this function only ever adjusts its own
    match_amount/lump_sum_amount fields, never the employee's."""
    employee_result = _employee_result(pretax=24_500.0)
    result = compute_employer_contribution(
        [employee_result],
        employer_plans={"you": (2.0, 1.0, 5_000.0)},
        member_earned_income={"you": 200_000.0},
        tax_year=2026,
    )
    assert employee_result.pretax_contributed == 24_500.0  # untouched
    assert result.member_results[0].person_name == "you"


def test_ineligible_member_gets_zero_for_both_pieces():
    """No earned_income this year -- never raises, just zero for both
    match and lump sum, regardless of what's configured."""
    employee = [_employee_result(pretax=0.0, eligible=False)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (0.5, 0.06, 5_000.0)},
        member_earned_income={"you": 0.0},
        tax_year=2026,
    )
    member = result.member_results[0]
    assert member.eligible is False
    assert member.match_amount == 0.0
    assert member.lump_sum_amount == 0.0
    assert member.rejected_reason is not None


def test_unconfigured_member_gets_zero_for_both_pieces():
    """A member present in contribution_results but with no entry (or
    None) in employer_plans contributes 0.0 for both pieces, never a
    KeyError."""
    employee = [_employee_result(pretax=20_000.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={},
        member_earned_income={"you": 150_000.0},
        tax_year=2026,
    )
    member = result.member_results[0]
    assert member.match_amount == 0.0
    assert member.lump_sum_amount == 0.0
    assert member.rejected_reason is None


def test_no_cross_member_contamination():
    employee = [_employee_result(person_name="you", pretax=20_000.0), _employee_result(person_name="spouse", pretax=0.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (0.5, 0.06, 1_000.0), "spouse": None},
        member_earned_income={"you": 150_000.0, "spouse": 100_000.0},
        tax_year=2026,
    )
    by_name = {r.person_name: r for r in result.member_results}
    assert by_name["you"].match_amount > 0.0
    assert by_name["spouse"].match_amount == 0.0
    assert by_name["spouse"].lump_sum_amount == 0.0


def test_nothing_configured_household_wide_never_consults_the_limit_figure():
    """Mirrors contribution_401k.py's own equivalent test: the unverified
    placeholder §415(c) limit must never be reported as "used" when no
    member has any employer contribution configured at all."""
    employee = [_employee_result(pretax=20_000.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": None},
        member_earned_income={"you": 150_000.0},
        tax_year=2026,
    )
    assert result.figures_used == []
    assert result.total_match == 0.0
    assert result.total_lump_sum == 0.0


def test_nothing_configured_never_raises_even_for_an_undocumented_tax_year():
    employee = [_employee_result(pretax=20_000.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": None},
        member_earned_income={"you": 150_000.0},
        tax_year=1999,
    )
    assert result.figures_used == []


def test_figures_used_reflects_the_limit_table_unverified_status():
    employee = [_employee_result(pretax=20_000.0)]
    result = compute_employer_contribution(
        employee,
        employer_plans={"you": (0.5, 0.06, 0.0)},
        member_earned_income={"you": 150_000.0},
        tax_year=2026,
    )
    assert len(result.figures_used) == 1
    assert result.figures_used[0].verified is False
    assert "415(c)" in result.figures_used[0].citation


def test_unsupported_tax_year_raises_only_when_something_is_configured():
    employee = [_employee_result(pretax=20_000.0)]
    with pytest.raises(UnsupportedTaxYearError):
        compute_employer_contribution(
            employee,
            employer_plans={"you": (0.5, 0.06, 0.0)},
            member_earned_income={"you": 150_000.0},
            tax_year=1999,
        )
