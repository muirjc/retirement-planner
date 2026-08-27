"""Unit tests for South Carolina's compute_tax() (US2).

Expected amounts are hand-calculated against this feature's own placeholder
SC bracket table and age-65 exclusion — see state/sc.py's docstring for why
the dollar figures are illustrative pending citation verification.
"""

from retirement_planner.tax import IncomeComponents
from retirement_planner.tax.state.sc import compute_tax


def test_sc_bracket_math_with_age_65_exclusion_both_filers():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert result.state == "SC"
    assert result.state_tax_owed == 1_278.64


def test_sc_no_exclusion_when_both_filers_under_65():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_tax(income, filer_ages=[50, 52], filing_status="married_filing_jointly", tax_year=2026)
    assert result.state_tax_owed == 3_198.64


def test_sc_social_security_is_not_taxed():
    """SC does not tax Social Security — only ordinary_income enters SC's
    taxable-income base."""
    with_ss = compute_tax(
        IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000),
        filer_ages=[50, 52],
        filing_status="married_filing_jointly",
        tax_year=2026,
    )
    without_ss = compute_tax(
        IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=0),
        filer_ages=[50, 52],
        filing_status="married_filing_jointly",
        tax_year=2026,
    )
    assert with_ss.state_tax_owed == without_ss.state_tax_owed


def test_sc_figures_used_includes_brackets_and_exclusion():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    figure_names = {f.name for f in result.figures_used}
    assert "sc_bracket_table" in figure_names
    assert "sc_age_65_exclusion" in figure_names
