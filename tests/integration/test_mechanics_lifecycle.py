"""Integration test: the full quickstart.md walkthrough for
003-retirement-account-mechanics (RMD table selection, swappable withdrawal
sequencing, swappable Roth conversion, and the RMD-not-convertible rule).

See specs/003-retirement-account-mechanics/quickstart.md — this test
exercises the same steps, updated for the `roth_balance` and
`rmd_figures_used` parameters added during implementation (see
roth_conversion.py and plan_year.py docstrings).
"""

import pytest

from retirement_planner.mechanics import (
    AccountBalances,
    compute_plan_year_mechanics,
    compute_rmd,
    compute_roth_conversion,
    compute_withdrawal_plan,
)


def test_step1_compute_an_rmd_with_the_correct_table():
    result = compute_rmd(traditional_balance=1_000_000, member_age=75, tax_year=2026)
    assert result.table_used == "uniform_lifetime"
    assert result.required_amount > 0

    joint_result = compute_rmd(
        traditional_balance=1_000_000,
        member_age=75,
        tax_year=2026,
        spouse_age=60,
        spouse_is_sole_beneficiary=True,
    )
    assert joint_result.table_used == "joint_life"
    assert joint_result.required_amount < result.required_amount

    too_young = compute_rmd(traditional_balance=1_000_000, member_age=60, tax_year=2026)
    assert too_young.required_amount == 0
    assert too_young.table_used is None


def test_step2_draw_funds_in_a_defined_swappable_sequence():
    balances = AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)

    plan = compute_withdrawal_plan(spending_need=80_000, rmd_amount=40_000, starting_balances=balances)
    assert plan.rmd_drawn == 40_000
    assert plan.sequence_withdrawals[0].account_type == "taxable"
    assert plan.shortfall == 0

    small_need_plan = compute_withdrawal_plan(
        spending_need=30_000, rmd_amount=40_000, starting_balances=balances
    )
    assert small_need_plan.sequence_withdrawals == []

    tiny_balances = AccountBalances(traditional=0, roth=0, taxable=1_000)
    shortfall_plan = compute_withdrawal_plan(spending_need=50_000, rmd_amount=0, starting_balances=tiny_balances)
    assert shortfall_plan.shortfall == 49_000
    assert shortfall_plan.ending_balances.taxable == 0


def test_step3_execute_a_roth_conversion_within_the_configured_window():
    # tax_year is held at 2026 because 002's tax figures currently document
    # only that year; plan_year (window membership) is independent of it.
    result = compute_roth_conversion(
        plan_year=2030,
        window=(2028, 2034),
        strategy="fill_to_bracket",
        bracket_ceiling_or_amount=206_000,
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=900_000,
        roth_balance=200_000,
    )
    assert result.amount_converted > 0
    assert result.amount_converted == result.ordinary_income_added

    outside_window = compute_roth_conversion(
        plan_year=2035,
        window=(2028, 2034),
        strategy="fill_to_bracket",
        bracket_ceiling_or_amount=206_000,
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2035,
        traditional_balance=900_000,
        roth_balance=200_000,
    )
    assert outside_window.amount_converted == 0

    fixed = compute_roth_conversion(
        plan_year=2030,
        window=(2028, 2034),
        strategy="fixed_amount",
        bracket_ceiling_or_amount=50_000,
        ordinary_income_established=120_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        tax_year=2026,
        traditional_balance=900_000,
        roth_balance=200_000,
    )
    assert fixed.amount_converted == 50_000
    assert result.amount_converted != fixed.amount_converted


def test_step4_rmd_dollars_are_never_also_converted():
    # tax_year is held at 2026 because 002's tax figures currently document
    # only that year; plan_year (window membership) is independent of it.
    result = compute_plan_year_mechanics(
        plan_year=2030,
        tax_year=2026,
        spending_need=60_000,
        starting_balances=AccountBalances(traditional=900_000, roth=200_000, taxable=50_000),
        rmd_amount=40_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        conversion_window=(2028, 2034),
        conversion_strategy="fill_to_bracket",
        conversion_bracket_ceiling_or_amount=206_000,
    )
    assert result.withdrawal_plan.rmd_drawn == 40_000
    assert result.conversion.ending_traditional_balance == pytest.approx(
        900_000 - 40_000 - result.conversion.amount_converted
    )
