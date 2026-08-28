"""Unit tests for compute_rmd() (US1).

Expected divisors/amounts are hand-calculated against this feature's own
placeholder tables (rmd.py) — see that module's docstring for why the
figures are illustrative pending citation verification; what's under test
here is the table-selection logic (Uniform Lifetime vs. Joint Life), not
that these specific numbers are IRS-official.
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
