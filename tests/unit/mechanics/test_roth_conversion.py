"""Unit tests for fill_to_bracket_ceiling(), fixed_dollar_amount(), and
compute_roth_conversion() (US3).
"""

import pytest

from retirement_planner.mechanics import compute_roth_conversion, fill_to_bracket_ceiling, fixed_dollar_amount
from retirement_planner.tax import IncomeComponents, compute_taxable_social_security


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


def test_fill_to_bracket_ceiling_can_overshoot_ceiling_when_conversion_crosses_ss_taxability_tier():
    """rp-8la (documented, bounded simplification -- not fixed): taxable
    Social Security is computed ONCE against ordinary_income_established
    (pre-conversion), never re-solved against the post-conversion total. A
    household whose pre-conversion provisional income sits below
    threshold_1 (0% SS taxable) sizes its conversion as if that stays 0%
    -- but a large enough conversion pushes the *real* provisional income
    (established + conversion + 0.5*benefit) past threshold_2 into the 85%
    tier, so the household's real total taxable income lands ABOVE the
    configured ceiling, not at it. This test pins today's actual behavior
    so a future change to this logic is deliberate, not a silent
    regression -- see docs/BRD.md §6.6.
    """
    established = 10_000.0
    benefit = 20_000.0
    ceiling = 100_000.0

    # Pre-conversion provisional income (established + 0.5*benefit =
    # 20,000) sits below MFJ's threshold_1 (32,000): the single pass sees
    # 0% of the benefit as taxable, so it sizes the conversion as if
    # income + conversion alone must reach the ceiling.
    pre_conversion_income = IncomeComponents(ordinary_income=established, social_security_gross_benefit=benefit)
    pre_conversion_taxable_ss, _ = compute_taxable_social_security(pre_conversion_income, "married_filing_jointly", 2026)
    assert pre_conversion_taxable_ss == 0.0

    result = fill_to_bracket_ceiling(
        ordinary_income_established=established,
        social_security_gross_benefit=benefit,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=500_000,
        roth_balance=0,
        ceiling=ceiling,
    )
    assert result.amount_converted == pytest.approx(90_000.0)

    # Real post-conversion provisional income (10,000 + 90,000 + 10,000 =
    # 110,000) is well past threshold_2 (44,000): 85% of the benefit is
    # actually taxable, not the 0% the sizing pass assumed.
    post_conversion_income = IncomeComponents(
        ordinary_income=established + result.amount_converted,
        social_security_gross_benefit=benefit,
    )
    real_taxable_ss, _ = compute_taxable_social_security(post_conversion_income, "married_filing_jointly", 2026)
    assert real_taxable_ss == pytest.approx(0.85 * benefit)

    real_total_taxable_income = established + result.amount_converted + real_taxable_ss
    assert real_total_taxable_income > ceiling
    assert real_total_taxable_income == pytest.approx(117_000.0)


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
