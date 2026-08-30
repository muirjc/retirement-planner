"""Unit tests for compute_rmd() (US1).

RMD_START_AGE and UNIFORM_LIFETIME_TABLE are IRS Pub. 590-B/26 U.S.C.
§401(a)(9)(C)(v)'s actual figures, cross-checked directly against those
primary sources (014-figure-verification, rp-9wi.5/.7); expected
divisors/amounts below use those real figures. JOINT_LIFE_TABLE remains
an illustrative placeholder outside that feature's scope (rmd.py's own
docstring) — what's under test for it here is still just the
table-selection logic (Uniform Lifetime vs. Joint Life), not that its
specific numbers are IRS-official.
"""

import pytest

from retirement_planner.mechanics import compute_rmd
from retirement_planner.tax import UnsupportedTaxYearError


def test_uniform_lifetime_table_used_for_a_filer_past_start_age():
    result = compute_rmd(traditional_balance=1_000_000, member_age=75, tax_year=2026)
    assert result.table_used == "uniform_lifetime"
    assert result.divisor == 24.6
    assert result.required_amount == pytest.approx(1_000_000 / 24.6)


def test_below_start_age_is_always_zero_with_no_table_lookup():
    result = compute_rmd(traditional_balance=1_000_000, member_age=60, tax_year=2026)
    assert result.required_amount == 0.0
    assert result.table_used is None
    assert result.divisor is None
    assert result.figures_used == []


def test_zero_traditional_balance_is_always_zero():
    result = compute_rmd(traditional_balance=0, member_age=80, tax_year=2026)
    assert result.required_amount == 0.0
    assert result.table_used is None


def test_joint_life_table_used_when_spouse_is_sole_beneficiary_and_more_than_10_years_younger():
    uniform_result = compute_rmd(traditional_balance=1_000_000, member_age=75, tax_year=2026)
    joint_result = compute_rmd(
        traditional_balance=1_000_000,
        member_age=75,
        tax_year=2026,
        spouse_age=60,
        spouse_is_sole_beneficiary=True,
    )
    assert joint_result.table_used == "joint_life"
    # The Joint Life divisor is always larger (younger joint life expectancy),
    # so the required amount is smaller for the same balance.
    assert joint_result.required_amount < uniform_result.required_amount


def test_uniform_lifetime_table_used_when_spouse_not_sole_beneficiary():
    result = compute_rmd(
        traditional_balance=1_000_000,
        member_age=75,
        tax_year=2026,
        spouse_age=60,
        spouse_is_sole_beneficiary=False,
    )
    assert result.table_used == "uniform_lifetime"


def test_uniform_lifetime_table_used_when_spouse_not_more_than_10_years_younger():
    result = compute_rmd(
        traditional_balance=1_000_000,
        member_age=75,
        tax_year=2026,
        spouse_age=68,
        spouse_is_sole_beneficiary=True,
    )
    assert result.table_used == "uniform_lifetime"


def test_figures_used_includes_start_age_and_table_used():
    result = compute_rmd(traditional_balance=1_000_000, member_age=75, tax_year=2026)
    figure_names = {f.name for f in result.figures_used}
    assert figure_names == {"rmd_start_age", "uniform_lifetime_table"}


def test_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_rmd(traditional_balance=1_000_000, member_age=75, tax_year=1999)


def test_rmd_start_age_and_uniform_lifetime_table_are_verified():
    """014-figure-verification (rp-9wi.5, rp-9wi.7)."""
    from retirement_planner.mechanics.rmd import RMD_START_AGE, UNIFORM_LIFETIME_TABLE

    assert RMD_START_AGE.verified is True
    assert UNIFORM_LIFETIME_TABLE.verified is True
    assert "26 U.S.C. §401(a)(9)(C)(v)" in RMD_START_AGE.citation
    assert "IRS Pub. 590-B" in UNIFORM_LIFETIME_TABLE.citation


def test_rmd_start_age_steps_from_73_to_75_in_2033():
    """014-figure-verification (rp-9wi.5): SECURE 2.0's scheduled 2033
    step is modeled, not silently flattened to one value forever."""
    from retirement_planner.mechanics.rmd import RMD_START_AGE

    assert RMD_START_AGE.value_for_year(2032) == 73
    assert RMD_START_AGE.value_for_year(2033) == 75

    # A 73-year-old owes an RMD the year before the step but not the year
    # of/after it, since 75 is the applicable age from 2033 on.
    assert compute_rmd(traditional_balance=500_000, member_age=73, tax_year=2032).required_amount > 0.0
    assert compute_rmd(traditional_balance=500_000, member_age=73, tax_year=2033).required_amount == 0.0


@pytest.mark.parametrize(
    "age,expected_divisor",
    [
        (72, 27.4),
        (75, 24.6),
        (90, 12.2),
        (100, 6.4),
        (101, 6.0),
        (110, 3.5),
        (120, 2.0),
    ],
)
def test_uniform_lifetime_divisors_match_irs_pub_590_b(age, expected_divisor):
    """014-figure-verification (rp-9wi.7): spot-checks against IRS Pub.
    590-B (2025), Appendix B, Table III directly, including ages beyond
    100 -- the table's own coverage gap this feature closes. Checked
    against the table itself, not through compute_rmd(), since age 72 is
    below every documented tax year's own RMD_START_AGE gate (73 or 75)
    and so is never reachable through compute_rmd() -- the table still
    documents its divisor, matching the published table's own coverage."""
    from retirement_planner.mechanics.rmd import UNIFORM_LIFETIME_TABLE

    assert UNIFORM_LIFETIME_TABLE.value_for_year(2026)[age] == expected_divisor


def test_age_over_100_no_longer_raises_a_lookup_error():
    """Before rp-9wi.7, member_age=101 (and above) had no entry in
    _UNIFORM_LIFETIME_DIVISORS and raised a plain KeyError -- not the
    typed UnsupportedTaxYearError compute_rmd() raises for an
    undocumented *year* (data-model.md). Now it succeeds."""
    result = compute_rmd(traditional_balance=500_000, member_age=101, tax_year=2026)
    assert result.divisor is not None
    assert result.required_amount == 500_000 / result.divisor
