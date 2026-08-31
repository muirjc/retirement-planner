"""Integration tests for the tax calculation engine: federal tax + Social
Security taxability, state tax through pluggable modules, and figure
provenance/scheduled rate changes. Sections are added incrementally as each
user story is implemented (US1, then US2, then US3), then Phase 6 adds the
full quickstart.md walkthrough.
"""

import pytest

from retirement_planner.tax import IncomeComponents, UnsupportedTaxYearError
from retirement_planner.tax.federal import compute_federal_tax
from retirement_planner.tax.state import compute_state_tax

# ---------------------------------------------------------------------------
# User Story 1: Compute accurate federal tax, including real Social
# Security taxability
# ---------------------------------------------------------------------------


def test_us1_federal_tax_across_all_three_provisional_income_tiers():
    """Acceptance Scenarios 1.1-1.4."""
    low_income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(low_income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert result.taxable_social_security == 0

    mid_income = IncomeComponents(ordinary_income=25_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(mid_income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert 0 < result.taxable_social_security <= 20_000 * 0.50

    high_income = IncomeComponents(ordinary_income=150_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(high_income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert result.taxable_social_security <= 20_000 * 0.85
    assert result.federal_tax_owed > 0


# ---------------------------------------------------------------------------
# User Story 2: Compute state tax through real, pluggable per-state modules
# ---------------------------------------------------------------------------


def test_us2_sc_de_nonzero_fl_zero_and_states_are_independent():
    """Acceptance Scenarios 2.1-2.4."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)

    sc_result = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    de_result = compute_state_tax("DE", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    fl_result = compute_state_tax("FL", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)

    assert sc_result.state_tax_owed > 0
    assert de_result.state_tax_owed > 0
    assert fl_result.state_tax_owed == 0
    assert fl_result.figures_used == []

    # Computing one state's tax never affects another's.
    sc_repeat = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert sc_repeat == sc_result


# ---------------------------------------------------------------------------
# User Story 3: See which figures are unverified, and get correct results
# across tax years with scheduled law changes
# ---------------------------------------------------------------------------


def test_us3_figure_provenance_schedule_change_and_out_of_range_year():
    """Acceptance Scenarios 3.1-3.4."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    sc_result = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)

    # Every figure behind the result is individually named, cited, dated,
    # and marked verified=False by default.
    for figure in sc_result.figures_used:
        assert figure.name and figure.citation and figure.last_verified is not None
        assert figure.verified is False

    # A documented multi-year schedule produces different, correct results
    # on either side of the scheduled change.
    result_2027 = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2027)
    assert result_2027.state_tax_owed != sc_result.state_tax_owed

    # A tax year outside any documented schedule is refused, not guessed.
    with pytest.raises(UnsupportedTaxYearError) as exc_info:
        compute_federal_tax(income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2075)
    assert exc_info.value.requested_year == 2075
    assert exc_info.value.available_years


# ---------------------------------------------------------------------------
# Phase 6: Polish & cross-cutting concerns
# ---------------------------------------------------------------------------


def test_quickstart_walkthrough_end_to_end():
    """Runs every step of quickstart.md as one sequence for a single
    household, confirming federal + every state's tax + figure provenance
    all compose correctly together, exactly as documented for a new user."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    ages = [67, 65]
    filing_status = "married_filing_jointly"

    # Step 1: federal tax, with real Social Security taxability.
    federal_result = compute_federal_tax(income, filer_ages=ages, filing_status=filing_status, tax_year=2026)
    assert federal_result.federal_tax_owed > 0
    assert 0 < federal_result.taxable_social_security <= income.social_security_gross_benefit * 0.85

    # Step 2: state tax through independent, pluggable modules — computed
    # for the *same* household as step 1, proving federal and state don't
    # interfere with each other.
    sc_result = compute_state_tax("SC", income, filer_ages=ages, filing_status=filing_status, tax_year=2026)
    de_result = compute_state_tax("DE", income, filer_ages=ages, filing_status=filing_status, tax_year=2026)
    fl_result = compute_state_tax("FL", income, filer_ages=ages, filing_status=filing_status, tax_year=2026)
    assert sc_result.state_tax_owed > 0
    assert de_result.state_tax_owed > 0
    assert fl_result.state_tax_owed == 0

    # Step 3: figure provenance on both the federal and state results, a
    # multi-year schedule change, and a refusal for an unsupported year.
    # federal_result's figures (SS thresholds + federal brackets) are now
    # verified (014-figure-verification, rp-9wi.1/.6); SC's own state-tax
    # figures remain out of scope for that feature and stay unverified.
    all_figures = federal_result.figures_used + sc_result.figures_used
    assert all(f.verified is True for f in federal_result.figures_used)
    assert all(f.verified is False for f in sc_result.figures_used)
    assert all(f.citation and f.last_verified for f in all_figures)

    sc_2027 = compute_state_tax("SC", income, filer_ages=ages, filing_status=filing_status, tax_year=2027)
    assert sc_2027.state_tax_owed != sc_result.state_tax_owed

    with pytest.raises(UnsupportedTaxYearError):
        compute_state_tax("SC", income, filer_ages=ages, filing_status=filing_status, tax_year=2075)
