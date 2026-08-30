"""Unit tests for compute_irmaa_surcharge() (010-advanced-tax-benefits, US1).

Expected amounts are hand-calculated against irmaa.py's actual CMS.gov
tax year 2026 IRMAA tier table, cross-checked directly against CMS's
published tables (014-figure-verification, rp-9wi.3).
"""

import pytest

from retirement_planner.tax import UnsupportedTaxYearError
from retirement_planner.tax.irmaa import compute_irmaa_surcharge


def test_magi_below_every_tier_has_no_surcharge():
    result = compute_irmaa_surcharge(
        magi=150_000.0, income_basis="two_year_lookback",
        filing_status="married_filing_jointly", tax_year=2026, enrolled_member_count=2,
    )
    assert result.tier_crossed is None
    assert result.surcharge_owed == 0.0


def test_magi_exactly_at_a_tier_threshold_triggers_that_tier():
    """Edge Cases: a tier's lower bound is inclusive."""
    result = compute_irmaa_surcharge(
        magi=218_000.0, income_basis="two_year_lookback",
        filing_status="married_filing_jointly", tax_year=2026, enrolled_member_count=1,
    )
    assert result.tier_crossed == 218_000.0
    assert result.surcharge_owed == 1_148.40


def test_magi_between_two_tiers_applies_the_lower_one():
    result = compute_irmaa_surcharge(
        magi=300_000.0, income_basis="two_year_lookback",
        filing_status="married_filing_jointly", tax_year=2026, enrolled_member_count=1,
    )
    assert result.tier_crossed == 274_000.0
    assert result.surcharge_owed == 2_884.80


def test_surcharge_scales_with_enrolled_member_count():
    result = compute_irmaa_surcharge(
        magi=300_000.0, income_basis="two_year_lookback",
        filing_status="married_filing_jointly", tax_year=2026, enrolled_member_count=2,
    )
    assert result.surcharge_owed == 2_884.80 * 2


def test_no_enrolled_member_means_no_surcharge_regardless_of_magi():
    """FR-004."""
    result = compute_irmaa_surcharge(
        magi=1_000_000.0, income_basis="two_year_lookback",
        filing_status="married_filing_jointly", tax_year=2026, enrolled_member_count=0,
    )
    assert result.tier_crossed is None
    assert result.surcharge_owed == 0.0


def test_income_basis_is_carried_through_unchanged():
    result = compute_irmaa_surcharge(
        magi=100_000.0, income_basis="current_year_proxy",
        filing_status="single", tax_year=2026, enrolled_member_count=1,
    )
    assert result.income_basis == "current_year_proxy"


def test_single_filer_uses_its_own_tier_table():
    result = compute_irmaa_surcharge(
        magi=109_000.0, income_basis="two_year_lookback",
        filing_status="single", tax_year=2026, enrolled_member_count=1,
    )
    assert result.tier_crossed == 109_000.0
    assert result.surcharge_owed == 1_148.40


def test_single_filer_surcharge_amount_matches_mfj_at_the_same_relative_tier():
    """014-figure-verification (rp-9wi.3): real IRMAA per-person surcharge
    amounts don't vary by filing status, only the MAGI threshold does --
    the old placeholder table incorrectly halved the single-filer amount."""
    mfj = compute_irmaa_surcharge(
        magi=218_000.0, income_basis="two_year_lookback",
        filing_status="married_filing_jointly", tax_year=2026, enrolled_member_count=1,
    )
    single = compute_irmaa_surcharge(
        magi=109_000.0, income_basis="two_year_lookback",
        filing_status="single", tax_year=2026, enrolled_member_count=1,
    )
    assert mfj.surcharge_owed == single.surcharge_owed == 1_148.40


def test_figures_used_reflects_the_tier_table_verification_status():
    result = compute_irmaa_surcharge(
        magi=150_000.0, income_basis="two_year_lookback",
        filing_status="married_filing_jointly", tax_year=2026, enrolled_member_count=1,
    )
    assert len(result.figures_used) == 1
    assert result.figures_used[0].verified is True
    assert "CMS.gov" in result.figures_used[0].citation


def test_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_irmaa_surcharge(
            magi=150_000.0, income_basis="two_year_lookback",
            filing_status="married_filing_jointly", tax_year=1999, enrolled_member_count=1,
        )
