"""Unit tests for compute_inherited_rmd() (012-inherited-ira-rmd, US1).

Expected divisors/amounts are hand-calculated against
inherited_rmd.py's SINGLE_LIFE_EXPECTANCY_TABLE, verified against IRS Pub.
590-B (2025), Appendix B, Table I (rp-6c5) -- age 80's divisor (11.2) is
this table's real, IRS-published value. What's under test here is the
"look up once at death_year + 1, then subtract 1.0 per subsequent year"
divisor logic (research.md §7).
"""

import pytest

from retirement_planner.mechanics.inherited_rmd import (
    SINGLE_LIFE_EXPECTANCY_TABLE,
    compute_inherited_rmd,
)
from retirement_planner.tax import UnsupportedTaxYearError

_COMMON_KWARGS = dict(
    death_year=2023,
    decedent_age_at_death=80,
    decedent_was_taking_rmds=True,
    beneficiary_classification="non_eligible_designated_beneficiary",
)


def test_initial_divisor_looked_up_at_decedent_age_for_the_year_after_death():
    result = compute_inherited_rmd(inherited_balance=1_000_000, tax_year=2024, **_COMMON_KWARGS)
    assert result.table_used == "single_life_expectancy"
    assert result.divisor == 11.2
    assert result.required_amount == pytest.approx(1_000_000 / 11.2)


def test_divisor_reduces_by_exactly_one_per_subsequent_year_not_a_fresh_lookup():
    year_1 = compute_inherited_rmd(inherited_balance=1_000_000, tax_year=2024, **_COMMON_KWARGS)
    year_2 = compute_inherited_rmd(inherited_balance=1_000_000, tax_year=2025, **_COMMON_KWARGS)
    year_3 = compute_inherited_rmd(inherited_balance=1_000_000, tax_year=2026, **_COMMON_KWARGS)
    assert year_1.divisor == 11.2
    assert year_2.divisor == 10.2
    assert year_3.divisor == 9.2


def test_zero_or_negative_balance_is_always_zero_with_no_table_lookup():
    result = compute_inherited_rmd(inherited_balance=0, tax_year=2024, **_COMMON_KWARGS)
    assert result.required_amount == 0.0
    assert result.table_used is None
    assert result.divisor is None
    assert result.figures_used == []


def test_depletion_deadline_is_death_year_plus_ten():
    result = compute_inherited_rmd(inherited_balance=1_000_000, tax_year=2024, **_COMMON_KWARGS)
    assert result.depletion_deadline_year == 2033


def test_is_within_ten_year_window_true_through_deadline_year_false_after():
    within = compute_inherited_rmd(inherited_balance=1_000_000, tax_year=2033, **_COMMON_KWARGS)
    after = compute_inherited_rmd(inherited_balance=1_000_000, tax_year=2034, **_COMMON_KWARGS)
    assert within.is_within_ten_year_window is True
    assert after.is_within_ten_year_window is False


def test_figures_used_includes_the_single_life_expectancy_table():
    result = compute_inherited_rmd(inherited_balance=1_000_000, tax_year=2024, **_COMMON_KWARGS)
    figure_names = {f.name for f in result.figures_used}
    assert figure_names == {"single_life_expectancy_table"}


def test_single_life_expectancy_table_is_verified_and_covers_every_published_age():
    """Regression for rp-6c5: the table previously covered only ages
    50-95 (a subset) and shipped verified=False; it now covers every age
    IRS Pub. 590-B (2025), Appendix B, Table I publishes (0-120+) and has
    been cross-checked against that primary source."""
    assert SINGLE_LIFE_EXPECTANCY_TABLE.verified is True
    divisors = SINGLE_LIFE_EXPECTANCY_TABLE.value_for_year(2024)
    assert set(divisors) == set(range(0, 121))
    # Spot-checked against IRS Pub. 590-B (2025) pp. 50-51.
    assert divisors[0] == 84.6
    assert divisors[50] == 36.2
    assert divisors[72] == 17.2
    assert divisors[80] == 11.2
    assert divisors[120] == 1.0


def test_unsupported_divisor_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_inherited_rmd(
            inherited_balance=1_000_000,
            tax_year=1999,
            death_year=1998,
            decedent_age_at_death=80,
            decedent_was_taking_rmds=True,
            beneficiary_classification="non_eligible_designated_beneficiary",
        )
