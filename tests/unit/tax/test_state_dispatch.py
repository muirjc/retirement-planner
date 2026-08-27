"""Unit tests for STATE_MODULES / compute_state_tax() dispatch (US2)."""

import pytest

from retirement_planner.tax import IncomeComponents
from retirement_planner.tax.state import STATE_MODULES, compute_state_tax


def test_state_modules_registry_has_sc_de_fl():
    assert set(STATE_MODULES.keys()) == {"SC", "DE", "FL"}


def test_compute_state_tax_dispatches_by_state_code():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    sc_result = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    fl_result = compute_state_tax("FL", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert sc_result.state == "SC"
    assert fl_result.state == "FL"
    assert sc_result.state_tax_owed != fl_result.state_tax_owed


def test_compute_state_tax_unknown_state_raises():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    with pytest.raises(KeyError):
        compute_state_tax("ZZ", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)


def test_computing_one_state_does_not_affect_another():
    """FR-005, Acceptance Scenario 2.4: independent modules, independent
    results — computing SC twice in between a DE call must not change."""
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)
    sc_first = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    compute_state_tax("DE", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    sc_second = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
    assert sc_first == sc_second
