"""Unit tests for Delaware's compute_tax() (US2).

Expected amounts are hand-calculated against this feature's own placeholder
DE bracket table and age-60 exclusion — see state/de.py's docstring for why
the dollar figures are illustrative pending citation verification.
"""

from retirement_planner.tax import IncomeComponents
from retirement_planner.tax.state.de import compute_tax


def test_de_bracket_math_with_age_60_exclusion_both_filers():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert result.state == "DE"
    assert result.state_tax_owed == 1_600.0


def test_de_no_exclusion_when_both_filers_under_60():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_tax(income, filer_ages=[45, 47], filing_status="married_filing_jointly", tax_year=2026)
    assert result.state_tax_owed > 1_600.0  # no exclusion applied -> higher taxable income


def test_de_figures_used_includes_brackets_and_exclusion():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    figure_names = {f.name for f in result.figures_used}
    assert "de_bracket_table" in figure_names
    assert "de_age_60_exclusion" in figure_names


def test_de_supports_a_realistic_multi_decade_plan_horizon():
    """rp-wif: the bracket table used to document only tax year 2026, so
    any plan year beyond 2026 raised UnsupportedTaxYearError -- a real
    household's plan horizon runs decades, not one year. Confirms a far-
    future tax year produces the same result as 2026 (the figures are
    held flat across the whole documented range, matching every other
    _DOCUMENTED_YEARS-based module)."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result_2026 = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    result_2050 = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2050)
    assert result_2050.state_tax_owed == result_2026.state_tax_owed == 1_600.0
