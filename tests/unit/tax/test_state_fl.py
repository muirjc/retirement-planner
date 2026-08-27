"""Unit tests for Florida's compute_tax() (US2) — a zero-income-tax state."""

from retirement_planner.tax import IncomeComponents
from retirement_planner.tax.state.fl import compute_tax


def test_fl_always_returns_zero_tax():
    income = IncomeComponents(ordinary_income=500_000, social_security_gross_benefit=50_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert result.state == "FL"
    assert result.state_tax_owed == 0.0


def test_fl_requires_no_figures():
    """FR-007: a zero-tax state must not require bracket/exclusion/citation
    data for figures it doesn't use."""
    income = IncomeComponents(ordinary_income=500_000, social_security_gross_benefit=50_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert result.figures_used == []


def test_fl_zero_tax_regardless_of_tax_year():
    """No figures means no schedule to be out-of-range for — FL should
    never raise UnsupportedTaxYearError."""
    income = IncomeComponents(ordinary_income=500_000, social_security_gross_benefit=50_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2075)
    assert result.state_tax_owed == 0.0
