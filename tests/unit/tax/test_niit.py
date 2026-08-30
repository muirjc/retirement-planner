"""Unit tests for compute_niit() (010-advanced-tax-benefits, US2).

Expected amounts are hand-calculated against the NIIT threshold/rate
figures (niit.py), which are fixed directly by 26 U.S.C. §1411 and have
been cross-checked against that statute's text
(014-figure-verification, rp-9wi.4).
"""

import pytest

from retirement_planner.tax import UnsupportedTaxYearError
from retirement_planner.tax.niit import compute_niit


def test_magi_at_threshold_has_no_surtax():
    """Edge Cases / data-model.md: the surtax applies only once MAGI
    exceeds the threshold -- "at" the threshold is not "above" it."""
    result = compute_niit(
        magi=250_000.0, investment_income=100_000.0, filing_status="married_filing_jointly", tax_year=2026,
    )
    assert result.threshold_exceeded is False
    assert result.surtax_owed == 0.0


def test_magi_below_threshold_has_no_surtax():
    result = compute_niit(
        magi=200_000.0, investment_income=100_000.0, filing_status="married_filing_jointly", tax_year=2026,
    )
    assert result.threshold_exceeded is False
    assert result.surtax_owed == 0.0


def test_surtax_applies_to_full_investment_income_when_it_is_the_lesser_amount():
    """MAGI exceeds threshold by 100,000; investment_income (30,000) is
    the lesser of the two -- the whole 30,000 is taxed at 3.8%."""
    result = compute_niit(
        magi=350_000.0, investment_income=30_000.0, filing_status="married_filing_jointly", tax_year=2026,
    )
    assert result.threshold_exceeded is True
    assert result.surtax_owed == pytest.approx(30_000.0 * 0.038)


def test_surtax_applies_only_to_the_amount_over_threshold_when_that_is_the_lesser_amount():
    """MAGI exceeds threshold by only 20,000; investment_income (100,000)
    is larger -- only the 20,000 excess is taxed, never the full
    investment_income (data-model.md's lesser-of rule)."""
    result = compute_niit(
        magi=270_000.0, investment_income=100_000.0, filing_status="married_filing_jointly", tax_year=2026,
    )
    assert result.threshold_exceeded is True
    assert result.surtax_owed == pytest.approx(20_000.0 * 0.038)


def test_zero_investment_income_has_no_surtax_even_above_threshold():
    result = compute_niit(
        magi=500_000.0, investment_income=0.0, filing_status="married_filing_jointly", tax_year=2026,
    )
    assert result.surtax_owed == 0.0


def test_single_filer_uses_its_own_lower_threshold():
    result = compute_niit(
        magi=220_000.0, investment_income=100_000.0, filing_status="single", tax_year=2026,
    )
    assert result.threshold_exceeded is True
    assert result.surtax_owed == pytest.approx(20_000.0 * 0.038)


def test_figures_used_are_verified_against_26_usc_1411():
    """014-figure-verification (rp-9wi.4): niit_threshold_mfj and niit_rate
    are cross-checked directly against 26 U.S.C. §1411(a)(1), (b)(1) --
    fixed by statute, not inflation-indexed."""
    result = compute_niit(
        magi=100_000.0, investment_income=0.0, filing_status="married_filing_jointly", tax_year=2026,
    )
    assert len(result.figures_used) == 2
    assert all(figure.verified is True for figure in result.figures_used)
    figures_by_name = {figure.name: figure for figure in result.figures_used}
    assert figures_by_name["niit_threshold_mfj"].citation == (
        "26 U.S.C. §1411(b)(1) — married filing jointly threshold ($250,000, fixed, not inflation-indexed)"
    )
    assert figures_by_name["niit_rate"].citation == "26 U.S.C. §1411(a)(1) — 3.8% surtax rate"


def test_unsupported_tax_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_niit(
            magi=300_000.0, investment_income=50_000.0, filing_status="married_filing_jointly", tax_year=1999,
        )
