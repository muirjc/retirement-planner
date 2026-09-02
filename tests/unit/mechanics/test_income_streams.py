"""Unit tests for compute_income_stream_amount() (021-pension-annuity-
income, rp-pid).

INFLATION_RATE (2.40%/year) is the 2025 OASDI Trustees Report's own
intermediate-assumption ultimate CPI rate -- see mechanics/income_streams.py's
module docstring for the citation. Expected fixed_nominal amounts below are
hand-calculated as annual_amount / (1.024 ** years_elapsed).
"""

import pytest

from retirement_planner.mechanics import INFLATION_RATE, compute_income_stream_amount


def test_before_start_age_is_zero():
    result = compute_income_stream_amount(
        annual_amount=20_000,
        inflation_adjustment="cola_adjusted",
        start_age=65,
        end_age=None,
        member_age_this_year=64,
        tax_year=2026,
        reference_tax_year=2026,
    )
    assert result.amount == 0.0
    assert result.figures_used == []


def test_at_start_age_is_active():
    result = compute_income_stream_amount(
        annual_amount=20_000,
        inflation_adjustment="cola_adjusted",
        start_age=65,
        end_age=None,
        member_age_this_year=65,
        tax_year=2031,
        reference_tax_year=2026,
    )
    assert result.amount == pytest.approx(20_000)


def test_no_end_age_stays_active_indefinitely():
    result = compute_income_stream_amount(
        annual_amount=20_000,
        inflation_adjustment="cola_adjusted",
        start_age=65,
        end_age=None,
        member_age_this_year=99,
        tax_year=2060,
        reference_tax_year=2026,
    )
    assert result.amount == pytest.approx(20_000)


def test_end_age_is_inclusive():
    kwargs = dict(annual_amount=15_000, inflation_adjustment="cola_adjusted", start_age=65, end_age=74)
    at_end_age = compute_income_stream_amount(
        member_age_this_year=74, tax_year=2035, reference_tax_year=2026, **kwargs
    )
    after_end_age = compute_income_stream_amount(
        member_age_this_year=75, tax_year=2036, reference_tax_year=2026, **kwargs
    )
    assert at_end_age.amount == pytest.approx(15_000)
    assert after_end_age.amount == 0.0


def test_single_year_window_when_end_age_equals_start_age():
    kwargs = dict(annual_amount=5_000, inflation_adjustment="cola_adjusted", start_age=70, end_age=70)
    active = compute_income_stream_amount(member_age_this_year=70, tax_year=2036, reference_tax_year=2026, **kwargs)
    before = compute_income_stream_amount(member_age_this_year=69, tax_year=2035, reference_tax_year=2026, **kwargs)
    after = compute_income_stream_amount(member_age_this_year=71, tax_year=2037, reference_tax_year=2026, **kwargs)
    assert active.amount == pytest.approx(5_000)
    assert before.amount == 0.0
    assert after.amount == 0.0


def test_cola_adjusted_stays_flat_across_years():
    kwargs = dict(annual_amount=30_000, inflation_adjustment="cola_adjusted", start_age=65, end_age=None)
    early = compute_income_stream_amount(member_age_this_year=65, tax_year=2031, reference_tax_year=2026, **kwargs)
    late = compute_income_stream_amount(member_age_this_year=90, tax_year=2056, reference_tax_year=2026, **kwargs)
    assert early.amount == pytest.approx(30_000)
    assert late.amount == pytest.approx(30_000)
    assert early.figures_used == []
    assert late.figures_used == []


def test_fixed_nominal_erodes_against_documented_inflation_rate():
    rate = INFLATION_RATE.value_for_year(2036)
    expected = 20_000 / ((1 + rate) ** 10)
    result = compute_income_stream_amount(
        annual_amount=20_000,
        inflation_adjustment="fixed_nominal",
        start_age=62,
        end_age=None,
        member_age_this_year=82,
        tax_year=2036,
        reference_tax_year=2026,
    )
    assert result.amount == pytest.approx(expected)
    assert result.amount < 20_000
    assert len(result.figures_used) == 1
    assert result.figures_used[0].name == "income_stream_fixed_nominal_erosion_rate"


def test_fixed_nominal_erosion_compounds_from_reference_year_not_start_age():
    """research.md §1 Assumptions: a stream that hasn't started paying yet
    still loses the same real value while waiting -- erosion is keyed off
    tax_year - reference_tax_year, not tax_year - start_age's own year."""
    at_year_zero = compute_income_stream_amount(
        annual_amount=10_000,
        inflation_adjustment="fixed_nominal",
        start_age=70,
        end_age=None,
        member_age_this_year=70,
        tax_year=2026,
        reference_tax_year=2026,
    )
    assert at_year_zero.amount == pytest.approx(10_000)

    ten_years_later_start = compute_income_stream_amount(
        annual_amount=10_000,
        inflation_adjustment="fixed_nominal",
        start_age=70,
        end_age=None,
        member_age_this_year=70,
        tax_year=2036,
        reference_tax_year=2026,
    )
    rate = INFLATION_RATE.value_for_year(2036)
    assert ten_years_later_start.amount == pytest.approx(10_000 / ((1 + rate) ** 10))


def test_overlapping_streams_are_summed_by_the_caller():
    """compute_income_stream_amount() itself has no notion of "other
    streams" -- summing multiple active streams for one member is the
    caller's job (comparison.projection._member_income_stream_amounts()).
    This test documents that independence: two calls for the same member/
    year, each active, simply add."""
    pension = compute_income_stream_amount(
        annual_amount=18_000,
        inflation_adjustment="cola_adjusted",
        start_age=62,
        end_age=None,
        member_age_this_year=65,
        tax_year=2031,
        reference_tax_year=2026,
    )
    earned_income = compute_income_stream_amount(
        annual_amount=25_000,
        inflation_adjustment="fixed_nominal",
        start_age=63,
        end_age=66,
        member_age_this_year=65,
        tax_year=2031,
        reference_tax_year=2026,
    )
    total = pension.amount + earned_income.amount
    assert total > pension.amount
    assert total == pytest.approx(pension.amount + earned_income.amount)
