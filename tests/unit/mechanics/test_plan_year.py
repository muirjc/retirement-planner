"""Unit tests for compute_plan_year_mechanics() (Edge Cases: RMD dollars are
never also converted).
"""

from datetime import date

import pytest

from retirement_planner.mechanics import AccountBalances, compute_plan_year_mechanics
from retirement_planner.tax import FigureUsage


def test_rmd_dollars_never_also_converted():
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
    # Conversion math started from the post-RMD traditional balance
    # (900_000 - 40_000), never from the pre-RMD 900_000.
    assert result.withdrawal_plan.rmd_drawn == 40_000
    assert result.conversion.ending_traditional_balance == pytest.approx(
        900_000 - 40_000 - result.conversion.amount_converted
    )


def test_no_conversion_plan_configured_yields_zeroed_conversion():
    result = compute_plan_year_mechanics(
        plan_year=2030,
        tax_year=2030,
        spending_need=60_000,
        starting_balances=AccountBalances(traditional=900_000, roth=200_000, taxable=50_000),
        rmd_amount=40_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        conversion_window=None,
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
    )
    assert result.conversion.amount_converted == 0.0


def test_ordinary_income_excludes_taxable_and_roth_draws():
    result = compute_plan_year_mechanics(
        plan_year=2030,
        tax_year=2030,
        spending_need=60_000,
        starting_balances=AccountBalances(traditional=900_000, roth=200_000, taxable=50_000),
        rmd_amount=40_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        conversion_window=None,
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
    )
    # spending_need=60_000 is fully covered by rmd_drawn (40_000) plus a
    # 20_000 taxable draw; only the RMD's traditional dollars count as
    # ordinary income.
    assert result.ordinary_income == 40_000


def test_rmd_figures_used_are_passed_through():
    result = compute_plan_year_mechanics(
        plan_year=2030,
        tax_year=2030,
        spending_need=60_000,
        starting_balances=AccountBalances(traditional=900_000, roth=200_000, taxable=50_000),
        rmd_amount=40_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        conversion_window=None,
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        rmd_figures_used=[],
    )
    assert result.figures_used == []


def test_omitted_inherited_distribution_parameters_reproduce_prior_behavior():
    # 012-inherited-ira-rmd (research.md §10): defaulting to 0.0/None must
    # be a strict no-op -- identical to every call above that never passes
    # them.
    result = compute_plan_year_mechanics(
        plan_year=2030,
        tax_year=2030,
        spending_need=60_000,
        starting_balances=AccountBalances(traditional=900_000, roth=200_000, taxable=50_000),
        rmd_amount=40_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        conversion_window=None,
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
    )
    assert result.ordinary_income == 40_000
    assert result.figures_used == []


def test_inherited_distribution_amount_included_in_ordinary_income():
    result = compute_plan_year_mechanics(
        plan_year=2030,
        tax_year=2030,
        spending_need=60_000,
        starting_balances=AccountBalances(traditional=900_000, roth=200_000, taxable=50_000),
        rmd_amount=40_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        conversion_window=None,
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        inherited_distribution_amount=25_000,
    )
    # spending_need=60_000 fully covered by rmd_drawn (40_000) + inherited
    # (25_000) alone -- no further sequence draws, so ordinary income is
    # exactly the sum of the two forced-draw sources.
    assert result.ordinary_income == 65_000
    assert result.withdrawal_plan.inherited_distribution_drawn == 25_000


def test_inherited_rmd_figures_used_are_unioned_into_result():
    figure = FigureUsage(
        name="single_life_expectancy_table",
        citation="IRS Pub. 590-B, Table I",
        last_verified=date(2026, 8, 28),
        verified=False,
    )
    result = compute_plan_year_mechanics(
        plan_year=2030,
        tax_year=2030,
        spending_need=60_000,
        starting_balances=AccountBalances(traditional=900_000, roth=200_000, taxable=50_000),
        rmd_amount=40_000,
        social_security_gross_benefit=0,
        filing_status="married_filing_jointly",
        conversion_window=None,
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        inherited_distribution_amount=25_000,
        inherited_rmd_figures_used=[figure],
    )
    assert figure in result.figures_used
