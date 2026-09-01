"""Unit tests for compute_early_withdrawal_penalty()
(020-early-withdrawal-penalty, rp-8z0, US1).

EARLY_WITHDRAWAL_PENALTY_RATE (10%) is cross-checked directly against
26 U.S.C. §72(t)(1)'s current text (early_withdrawal_penalty.py's own
module docstring).
"""

import pytest

from retirement_planner.tax import UnsupportedTaxYearError
from retirement_planner.tax.early_withdrawal_penalty import compute_early_withdrawal_penalty


def test_penalty_is_ten_percent_of_a_positive_base():
    """spec.md Acceptance Scenario US1.1."""
    result = compute_early_withdrawal_penalty(taxable_early_distribution_base=20_000.0, tax_year=2026)
    assert result.taxable_early_distribution_base == 20_000.0
    assert result.penalty_owed == pytest.approx(2_000.0)


def test_zero_base_has_zero_penalty_but_figures_used_still_populated():
    """research.md Decision 5: figures_used is always populated, even
    when the base is 0.0 -- mirrors compute_niit()'s own "always cited"
    precedent, unlike 019's own conditional-citation convention."""
    result = compute_early_withdrawal_penalty(taxable_early_distribution_base=0.0, tax_year=2026)
    assert result.penalty_owed == 0.0
    assert len(result.figures_used) == 1
    assert result.figures_used[0].name == "early_withdrawal_penalty_rate"


def test_figures_used_carries_the_expected_citation_and_verified_flag():
    """spec.md FR-009, User Story 3: the figure cites its governing
    statute and carries a last_verified date, matching this project's
    existing regulated-figure convention."""
    result = compute_early_withdrawal_penalty(taxable_early_distribution_base=1_000.0, tax_year=2026)
    usage = result.figures_used[0]
    assert usage.name == "early_withdrawal_penalty_rate"
    assert "72(t)(1)" in usage.citation
    assert "59" in usage.citation  # the age-59½ exception is cited too
    assert usage.verified is True
    assert usage.last_verified is not None


def test_rate_is_fixed_across_documented_years():
    """26 U.S.C. §72(t)(1)'s 10% rate is fixed by statute, not
    inflation-indexed -- same rate every documented year."""
    for tax_year in (2020, 2026, 2050, 2074):
        result = compute_early_withdrawal_penalty(taxable_early_distribution_base=10_000.0, tax_year=tax_year)
        assert result.penalty_owed == pytest.approx(1_000.0)


def test_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_early_withdrawal_penalty(taxable_early_distribution_base=10_000.0, tax_year=1999)
