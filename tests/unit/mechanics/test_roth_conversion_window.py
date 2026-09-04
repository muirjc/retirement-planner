"""Unit tests for resolve_gap_window() (rp-nui) -- the auto-derived
("gap-year") Roth conversion window.

All cases use reference_tax_year=2026 throughout, so the RMD-eligibility
years they exercise mirror test_rmd.py's own worked age-73/75-boundary
examples (current_age=67 -> eligible 2032; current_age=60 -> eligible 2041,
since that member turns 73 in 2039, already past the 2033 step, so 75
applies)."""

import pytest

from retirement_planner.mechanics import GapWindowMemberInputs, resolve_gap_window
from retirement_planner.tax import UnsupportedTaxYearError


def test_single_member_normal_gap():
    """Wages end at 65 (current_age=60 -> wage-end tax year 2031), RMD
    eligibility at 2041 (see module docstring) -- window opens the year
    after wages stop and closes the year before RMD eligibility."""
    member = GapWindowMemberInputs(current_age=60, latest_wage_end_age=65)
    window, figures = resolve_gap_window([member], reference_tax_year=2026)
    assert window == (2032, 2040)
    assert {f.name for f in figures} == {"rmd_start_age"}


def test_no_earned_income_at_all_opens_the_window_immediately():
    """A member with no earned_income streams is represented by the
    caller as latest_wage_end_age == current_age - 1 -- wages "already
    stopped" as of the run's own start."""
    member = GapWindowMemberInputs(current_age=60, latest_wage_end_age=59)
    window, _figures = resolve_gap_window([member], reference_tax_year=2026)
    assert window == (2026, 2040)


def test_wages_never_stop_returns_none():
    member = GapWindowMemberInputs(current_age=60, latest_wage_end_age=None)
    window, figures = resolve_gap_window([member], reference_tax_year=2026)
    assert window is None
    assert figures == []  # RMD_START_AGE never consulted -- short-circuited before that


def test_wages_end_after_rmd_age_returns_none():
    """current_age=70, wages end at 80 -> wage-end year 2036, window
    would start 2037 -- but this member's own RMD eligibility (73 before
    the 2033 step) is 2029, window_end=2028. window_start > window_end ->
    no chronological gap exists."""
    member = GapWindowMemberInputs(current_age=70, latest_wage_end_age=80)
    window, figures = resolve_gap_window([member], reference_tax_year=2026)
    assert window is None
    # RMD_START_AGE WAS consulted here (window_end is computed before the
    # emptiness check) -- distinguishes this from the never-stops case above.
    assert {f.name for f in figures} == {"rmd_start_age"}


def test_two_member_wage_stacking_guard_uses_the_later_members_stop_year():
    """Member a's wages stop first (2031); member b's stop later (2036).
    The window must not open until BOTH have stopped -- opening at 2032
    (right after `a` alone) would still layer conversions on top of `b`'s
    active wages, which are pooled into the same ordinary_income_established
    total fill_to_bracket_ceiling() sizes against."""
    a = GapWindowMemberInputs(current_age=60, latest_wage_end_age=65)  # stops 2031
    b = GapWindowMemberInputs(current_age=58, latest_wage_end_age=68)  # stops 2036
    window, _figures = resolve_gap_window([a, b], reference_tax_year=2026)
    assert window is not None
    assert window[0] == 2037  # the year after the LATER stop year (2036), not the earlier (2031)


def test_household_level_window_uses_the_earliest_members_rmd_eligibility():
    """Conservative: the window closes at the EARLIEST RMD-eligible
    member's own eligibility year, even if another member's own account
    ownership share is what actually matters for the pooled traditional
    balance -- resolve_gap_window() has no traditional_ownership_shares
    input at all (a comparison-layer concept), so it can't distinguish;
    documented as a deliberate simplification."""
    a = GapWindowMemberInputs(current_age=60, latest_wage_end_age=59)  # RMD-eligible 2041
    b = GapWindowMemberInputs(current_age=67, latest_wage_end_age=59)  # RMD-eligible 2032 (earlier)
    window, _figures = resolve_gap_window([a, b], reference_tax_year=2026)
    assert window is not None
    assert window[1] == 2031  # closes the year before member b's own (earlier) RMD eligibility


def test_empty_members_list_returns_none():
    window, figures = resolve_gap_window([], reference_tax_year=2026)
    assert window is None
    assert figures == []


def test_raises_unsupported_tax_year_for_an_undocumented_reference_year():
    member = GapWindowMemberInputs(current_age=60, latest_wage_end_age=65)
    with pytest.raises(UnsupportedTaxYearError):
        resolve_gap_window([member], reference_tax_year=1999)
