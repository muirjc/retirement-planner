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
