"""Unit tests for figure provenance and scheduled rate changes (US3)."""

import pytest

from retirement_planner.tax import IncomeComponents, UnsupportedTaxYearError
from retirement_planner.tax.federal import compute_federal_tax
from retirement_planner.tax.state import compute_state_tax


def test_every_figure_used_carries_citation_date_and_verified_status():
    """FR-009-FR-011, Acceptance Scenarios 3.1-3.2."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)

    assert len(result.figures_used) == 2
    for figure in result.figures_used:
        assert figure.name
        assert figure.citation
        assert figure.last_verified is not None
        assert figure.verified is False  # nothing ships pre-confirmed by default


def test_federal_result_figures_are_also_individually_traceable():
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert len(result.figures_used) == 3  # SS thresholds + federal brackets + standard deduction
    # All verified against their primary sources (014-figure-verification,
    # rp-9wi.1/.6; rp-7me) -- unlike SC's own state-tax figures above, which
    # remain out of scope and unverified.
    assert all(f.verified is True for f in result.figures_used)


def test_sc_scheduled_rate_change_produces_different_results_2026_vs_2027():
    """FR-012, Acceptance Scenario 3.3: same household, two documented
    years on either side of a scheduled change -> different, independently
    correct results."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    result_2026 = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    result_2027 = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2027)

    assert result_2026.state_tax_owed == 1_278.64
    assert result_2027.state_tax_owed == 1_222.80
    assert result_2026.state_tax_owed != result_2027.state_tax_owed


def test_out_of_schedule_tax_year_raises_with_actionable_detail():
    """FR-016, Acceptance Scenario 3.4: a year far outside any documented
    schedule is refused, not extrapolated, and the error names the figure,
    requested year, and the years that are documented."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)

    with pytest.raises(UnsupportedTaxYearError) as exc_info:
        compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2075)

    assert exc_info.value.requested_year == 2075
    assert exc_info.value.figure_name
    assert 2026 in exc_info.value.available_years
    assert 2027 in exc_info.value.available_years


def test_out_of_schedule_year_before_earliest_documented_year_also_raises():
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
    with pytest.raises(UnsupportedTaxYearError):
        compute_federal_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=1999)
