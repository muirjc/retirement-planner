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


def test_sc_supports_a_realistic_multi_decade_plan_horizon():
    """rp-wif: the bracket table used to document only 2026-2027, so any
    plan year beyond 2027 raised UnsupportedTaxYearError -- a real
    household's plan horizon runs decades, not 1-2 years. Confirms a far-
    future tax year works (holding the 2027 scheduled-change rate flat,
    same as every other _DOCUMENTED_YEARS-based module) without touching
    the 2026/2027 illustrative-rate-change behavior itself (still covered
    by test_figure_tracking.py's own dedicated test)."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2050)
    assert result.state_tax_owed == 1_222.80  # same as the 2027 rate (held flat from 2027 on)


def test_sc_retains_taxable_income_exclusion_applied_and_bracket_breakdown():
    """rp-bm8.3: same worked example as
    test_sc_bracket_math_with_age_65_exclusion_both_filers() ($60,000
    ordinary income, both filers 65+ -> $30,000 exclusion, $30,000 taxable,
    $1,278.64 owed) -- asserts the previously-discarded intermediate
    values are now retained."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)

    assert result.exclusion_applied == 30_000.0  # 2 filers x $15,000
    assert result.taxable_income == 30_000.0  # 60,000 - 30,000
    rows = [(row.rate, row.income_in_bracket, row.tax_in_bracket) for row in result.bracket_breakdown]
    # SC's own $0-rate first bracket (0% up to $3,200) is included -- income
    # reached it, even though it contributed $0 tax; only brackets the
    # taxable_income never reached at all are omitted.
    assert rows == [(0.00, 3_200.0, 0.0), (0.03, 12_840.0, 385.2), (0.064, 13_960.0, 893.44)]
    assert sum(row.tax_in_bracket for row in result.bracket_breakdown) == result.state_tax_owed


def test_sc_exclusion_applied_is_zero_when_no_filer_qualifies():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_tax(income, filer_ages=[50, 52], filing_status="married_filing_jointly", tax_year=2026)
    assert result.exclusion_applied == 0.0
    assert result.taxable_income == 60_000.0


def test_sc_ignores_government_pension_income():
    """027-nc-bailey-exclusion: government_pension_income is a NC-only
    (Bailey settlement) field -- SC never reads it, so a nonzero value
    changes nothing (spec.md FR-006)."""
    with_field = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000, government_pension_income=40_000)
    without_field = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result_with = compute_tax(with_field, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    result_without = compute_tax(without_field, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert result_with.state_tax_owed == result_without.state_tax_owed
