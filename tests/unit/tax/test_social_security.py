"""Unit tests for compute_taxable_social_security() (US1).

Expected values are hand-calculated against the actual federal provisional-
income formula (26 U.S.C. §86): thresholds $32,000/$44,000 for MFJ and
$25,000/$34,000 for single are the real, longstanding statutory base
amounts (see quickstart.md) — this is why compute_taxable_social_security()
can be tested precisely even though this feature's bracket *tables*
(federal.py, state modules) use illustrative placeholder figures.
"""

import pytest

from retirement_planner.tax import IncomeComponents, UnsupportedTaxYearError
from retirement_planner.tax.social_security import compute_taxable_social_security


def test_below_first_threshold_mfj_is_not_taxable():
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
    taxable, figures = compute_taxable_social_security(income, "married_filing_jointly", 2026)
    assert taxable == 0.0
    assert len(figures) == 1
    assert figures[0].name == "ss_provisional_income_thresholds_mfj"


def test_between_thresholds_mfj_partially_taxable():
    income = IncomeComponents(ordinary_income=25_000, social_security_gross_benefit=20_000)
    taxable, _ = compute_taxable_social_security(income, "married_filing_jointly", 2026)
    assert taxable == 1_500.0
    assert taxable <= 0.5 * income.social_security_gross_benefit


def test_above_second_threshold_mfj_capped_at_85_percent():
    income = IncomeComponents(ordinary_income=150_000, social_security_gross_benefit=20_000)
    taxable, _ = compute_taxable_social_security(income, "married_filing_jointly", 2026)
    assert taxable == 17_000.0
    assert taxable == 0.85 * income.social_security_gross_benefit
    assert taxable <= 0.85 * income.social_security_gross_benefit  # never more


def test_below_first_threshold_single_is_not_taxable():
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
    taxable, _ = compute_taxable_social_security(income, "single", 2026)
    assert taxable == 0.0


def test_between_thresholds_single_partially_taxable():
    income = IncomeComponents(ordinary_income=20_000, social_security_gross_benefit=20_000)
    taxable, _ = compute_taxable_social_security(income, "single", 2026)
    assert taxable == 2_500.0


def test_zero_social_security_benefit_is_not_taxable():
    income = IncomeComponents(ordinary_income=150_000, social_security_gross_benefit=0)
    taxable, _ = compute_taxable_social_security(income, "married_filing_jointly", 2026)
    assert taxable == 0.0


def test_unsupported_tax_year_raises():
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
    with pytest.raises(UnsupportedTaxYearError) as exc_info:
        compute_taxable_social_security(income, "married_filing_jointly", 2075)
    assert exc_info.value.requested_year == 2075
    assert 2026 in exc_info.value.available_years
