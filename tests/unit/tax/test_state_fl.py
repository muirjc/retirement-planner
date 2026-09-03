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


def test_fl_taxable_income_exclusion_and_bracket_breakdown_are_trivially_zero():
    """rp-bm8.3: FL's compute_tax() never runs bracket math at all -- the
    new fields get StateTaxResult's own defaults (0.0, 0.0, []), not a
    fabricated computation."""
    income = IncomeComponents(ordinary_income=500_000, social_security_gross_benefit=50_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert result.taxable_income == 0.0
    assert result.exclusion_applied == 0.0
    assert result.bracket_breakdown == []


def test_fl_ignores_government_pension_income():
    """027-nc-bailey-exclusion: government_pension_income is a NC-only
    (Bailey settlement) field -- FL never reads it, so a nonzero value
    changes nothing (spec.md FR-006)."""
    income = IncomeComponents(ordinary_income=500_000, social_security_gross_benefit=50_000, government_pension_income=100_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert result.state_tax_owed == 0.0
