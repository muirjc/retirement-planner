"""Unit tests for fill_to_bracket_ceiling(), fixed_dollar_amount(), and
compute_roth_conversion() (US3).
"""

import pytest

from retirement_planner.mechanics import compute_roth_conversion, fill_to_bracket_ceiling, fixed_dollar_amount


def test_fill_to_bracket_ceiling_fills_up_to_the_configured_ceiling():
    result = fill_to_bracket_ceiling(
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=900_000,
        roth_balance=200_000,
        ceiling=206_000,
    )
    assert result.amount_converted == pytest.approx(86_000)
    assert result.ordinary_income_added == result.amount_converted
    assert result.ending_roth_balance == pytest.approx(286_000)
    assert result.ending_traditional_balance == pytest.approx(814_000)


def test_fill_to_bracket_ceiling_returns_zero_not_negative_when_income_already_meets_ceiling():
    result = fill_to_bracket_ceiling(
        ordinary_income_established=250_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=900_000,
        roth_balance=0,
        ceiling=206_000,
    )
    assert result.amount_converted == 0.0


def test_fixed_dollar_amount_converts_exactly_the_configured_amount():
    result = fixed_dollar_amount(
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=900_000,
        roth_balance=0,
        fixed_amount=50_000,
    )
    assert result.amount_converted == 50_000
    assert result.ending_traditional_balance == 850_000


def test_fixed_dollar_amount_capped_at_remaining_traditional_balance():
    result = fixed_dollar_amount(
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=30_000,
        roth_balance=0,
        fixed_amount=50_000,
    )
    assert result.amount_converted == 30_000
    assert result.ending_traditional_balance == 0


def test_compute_roth_conversion_zero_outside_window():
    result = compute_roth_conversion(
        plan_year=2035,
        window=(2028, 2034),
        strategy="fill_to_bracket",
        bracket_ceiling_or_amount=206_000,
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2035,
        traditional_balance=900_000,
        roth_balance=0,
    )
    assert result.amount_converted == 0.0
    assert result.figures_used == []


def test_compute_roth_conversion_zero_when_no_conversion_plan_configured():
    result = compute_roth_conversion(
        plan_year=2030,
        window=None,
        strategy=None,
        bracket_ceiling_or_amount=None,
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2030,
        traditional_balance=900_000,
        roth_balance=0,
    )
    assert result.amount_converted == 0.0


def test_compute_roth_conversion_nonzero_at_window_boundaries():
    # plan_year (window membership) and tax_year (rate-table lookup) are
    # independent parameters — tax_year is held at 2026 here because 002's
    # tax figures currently document only that year (see 002's contract
    # note on callers needing years beyond a figure's documented schedule).
    first_year = compute_roth_conversion(
        plan_year=2028,
        window=(2028, 2034),
        strategy="fill_to_bracket",
        bracket_ceiling_or_amount=206_000,
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=900_000,
        roth_balance=0,
    )
    last_year = compute_roth_conversion(
        plan_year=2034,
        window=(2028, 2034),
        strategy="fill_to_bracket",
        bracket_ceiling_or_amount=206_000,
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=900_000,
        roth_balance=0,
    )
    assert first_year.amount_converted > 0
    assert last_year.amount_converted > 0


def test_conversion_amount_never_exceeds_traditional_balance_for_either_strategy():
    bracket = fill_to_bracket_ceiling(
        ordinary_income_established=0,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=10_000,
        roth_balance=0,
        ceiling=206_000,
    )
    fixed = fixed_dollar_amount(
        ordinary_income_established=0,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=10_000,
        roth_balance=0,
        fixed_amount=50_000,
    )
    assert bracket.amount_converted <= 10_000
    assert fixed.amount_converted <= 10_000


def test_two_strategies_produce_different_independently_correct_amounts():
    bracket = fill_to_bracket_ceiling(
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=900_000,
        roth_balance=0,
        ceiling=206_000,
    )
    fixed = fixed_dollar_amount(
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=900_000,
        roth_balance=0,
        fixed_amount=50_000,
    )
    assert bracket.amount_converted != fixed.amount_converted


def test_unregistered_strategy_raises_keyerror():
    with pytest.raises(KeyError):
        compute_roth_conversion(
            plan_year=2030,
            window=(2028, 2034),
            strategy="nope",
            bracket_ceiling_or_amount=1_000,
            ordinary_income_established=0,
            social_security_gross_benefit=0,
            filing_status="married_filing_jointly",
            tax_year=2030,
            traditional_balance=900_000,
            roth_balance=0,
        )
