"""Unit tests for North Carolina's compute_tax() (024-nc-state-tax).

Unlike SC's/DE's placeholder bracket tables, NC's flat rate is a real,
confirmed figure (verified=True) -- see nc.py's docstring and
specs/024-nc-state-tax/research.md §2 for the NCDOR/statute citation these
expected amounts are checked against.
"""

import pytest

from retirement_planner.tax import IncomeComponents, UnsupportedTaxYearError
from retirement_planner.tax.state.nc import compute_tax


def test_nc_zero_income_floor():
    income = IncomeComponents(ordinary_income=0.0, social_security_gross_benefit=0.0)
    result = compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2026)
    assert result.state == "NC"
    assert result.state_tax_owed == 0.0


def test_nc_tax_year_2026_flat_399_percent():
    income = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
    result = compute_tax(income, filer_ages=[67], filing_status="married_filing_jointly", tax_year=2026)
    assert result.state_tax_owed == pytest.approx(80_000.0 * 0.0399)


def test_nc_tax_year_2025_flat_425_percent():
    """The legislated rate one year ahead of the 2026 step-down."""
    income = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
    result = compute_tax(income, filer_ages=[67], filing_status="married_filing_jointly", tax_year=2025)
    assert result.state_tax_owed == pytest.approx(80_000.0 * 0.0425)
    later = compute_tax(income, filer_ages=[67], filing_status="married_filing_jointly", tax_year=2026)
    assert result.state_tax_owed > later.state_tax_owed


def test_nc_social_security_is_not_taxed():
    """NC does not tax Social Security — only ordinary_income enters NC's
    taxable-income base."""
    with_ss = compute_tax(
        IncomeComponents(ordinary_income=50_000.0, social_security_gross_benefit=30_000.0),
        filer_ages=[67],
        filing_status="single",
        tax_year=2026,
    )
    without_ss = compute_tax(
        IncomeComponents(ordinary_income=50_000.0, social_security_gross_benefit=0.0),
        filer_ages=[67],
        filing_status="single",
        tax_year=2026,
    )
    assert with_ss.state_tax_owed == without_ss.state_tax_owed == pytest.approx(50_000.0 * 0.0399)


def test_nc_no_age_based_exclusion():
    """Unlike SC (age 65) and DE (age 60), NC applies no age-based
    exclusion at all — an over-65 household is taxed on 100% of ordinary
    income, same as a household of 30-year-olds (spec.md FR-006)."""
    income = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
    older = compute_tax(income, filer_ages=[70, 68], filing_status="married_filing_jointly", tax_year=2026)
    younger = compute_tax(income, filer_ages=[30, 32], filing_status="married_filing_jointly", tax_year=2026)
    assert older.state_tax_owed == younger.state_tax_owed == pytest.approx(80_000.0 * 0.0399)


def test_nc_no_bracket_cliff_at_high_income():
    """A flat rate applies uniformly with no additional top bracket, unlike
    SC's/DE's graduated tables — confirm no cliff artifact at a high
    income."""
    income = IncomeComponents(ordinary_income=2_000_000.0, social_security_gross_benefit=0.0)
    result = compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2026)
    assert result.state_tax_owed == pytest.approx(2_000_000.0 * 0.0399)


def test_nc_unsupported_tax_year_raises():
    income = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
    with pytest.raises(UnsupportedTaxYearError):
        compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2019)


def test_nc_figures_used_includes_flat_rate():
    income = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
    result = compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2026)
    figure_names = {f.name for f in result.figures_used}
    assert figure_names == {"nc_flat_rate"}
    figure = result.figures_used[0]
    assert figure.verified is True


def test_nc_supports_a_realistic_multi_decade_plan_horizon():
    """Mirrors sc.py's own rp-wif regression test: a far-future tax year
    must not raise UnsupportedTaxYearError (holds the 2026 rate flat)."""
    income = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
    result = compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2050)
    assert result.state_tax_owed == pytest.approx(80_000.0 * 0.0399)


# --- 027-nc-bailey-exclusion ---------------------------------------------


def test_nc_bailey_qualifying_income_is_excluded_from_taxable_base():
    """spec.md Acceptance Scenario 1: $40k Bailey-qualifying pension + $30k
    other ordinary income -- only the $30k is taxed."""
    income = IncomeComponents(
        ordinary_income=70_000.0,
        social_security_gross_benefit=0.0,
        government_pension_income=40_000.0,
    )
    result = compute_tax(income, filer_ages=[67], filing_status="married_filing_jointly", tax_year=2026)
    assert result.state_tax_owed == pytest.approx(30_000.0 * 0.0399)


def test_nc_fully_bailey_qualifying_income_is_untaxed():
    """spec.md Acceptance Scenario 2: 100% Bailey-qualifying -> $0 NC tax."""
    income = IncomeComponents(
        ordinary_income=50_000.0,
        social_security_gross_benefit=0.0,
        government_pension_income=50_000.0,
    )
    result = compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2026)
    assert result.state_tax_owed == 0.0


def test_nc_no_bailey_qualifying_income_is_unchanged_from_original_behavior():
    """spec.md Acceptance Scenario 3 / FR-002: government_pension_income left
    at its 0.0 default reproduces 024-nc-state-tax's original behavior
    exactly."""
    income = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
    result = compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2026)
    assert result.state_tax_owed == pytest.approx(80_000.0 * 0.0399)


def test_nc_bailey_exclusion_floors_taxable_base_at_zero():
    """Edge Cases: government_pension_income exceeding ordinary_income (e.g.
    a stream that hasn't fully wound down while other income has) never
    produces a negative taxable base."""
    income = IncomeComponents(
        ordinary_income=20_000.0,
        social_security_gross_benefit=0.0,
        government_pension_income=25_000.0,
    )
    result = compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2026)
    assert result.state_tax_owed == 0.0


def test_nc_retains_taxable_income_exclusion_applied_and_bracket_breakdown():
    """rp-bm8.3: same worked example as
    test_nc_bailey_qualifying_income_is_excluded_from_taxable_base()
    ($40k Bailey-qualifying excluded from $70k ordinary income -> $30k
    taxable at the flat 3.99% rate)."""
    income = IncomeComponents(
        ordinary_income=70_000.0,
        social_security_gross_benefit=0.0,
        government_pension_income=40_000.0,
    )
    result = compute_tax(income, filer_ages=[67], filing_status="married_filing_jointly", tax_year=2026)

    assert result.exclusion_applied == 40_000.0
    assert result.taxable_income == 30_000.0
    assert len(result.bracket_breakdown) == 1
    row = result.bracket_breakdown[0]
    assert (row.rate, row.income_in_bracket) == (0.0399, 30_000.0)
    assert row.tax_in_bracket == pytest.approx(30_000.0 * 0.0399)
    assert result.bracket_breakdown[0].tax_in_bracket == result.state_tax_owed


def test_nc_bracket_breakdown_is_empty_when_fully_excluded():
    income = IncomeComponents(
        ordinary_income=50_000.0,
        social_security_gross_benefit=0.0,
        government_pension_income=50_000.0,
    )
    result = compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2026)
    assert result.taxable_income == 0.0
    assert result.bracket_breakdown == []


def test_nc_bailey_exclusion_figures_used_unchanged():
    """No new SourcedFigure is introduced for the Bailey exclusion
    (research.md §4) -- figures_used still cites only the flat rate."""
    income = IncomeComponents(
        ordinary_income=70_000.0,
        social_security_gross_benefit=0.0,
        government_pension_income=40_000.0,
    )
    result = compute_tax(income, filer_ages=[67], filing_status="single", tax_year=2026)
    figure_names = {f.name for f in result.figures_used}
    assert figure_names == {"nc_flat_rate"}
