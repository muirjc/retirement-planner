"""Unit tests for compute_federal_tax() (US1).

Expected tax amounts are hand-calculated against federal.py's actual IRS
Rev. Proc. 2025-32 tax year 2026 bracket tables (014-figure-verification,
rp-9wi.1) — what's under test here is that the *math* (progressive
brackets + real SS taxability) is genuine, not merely that these
specific numbers are IRS-official (they now are).
"""

from retirement_planner.tax import IncomeComponents
from retirement_planner.tax.federal import compute_federal_tax


def test_federal_tax_is_genuine_progressive_bracket_math_mfj():
    """Low income: taxable income stays entirely in the first bracket."""
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(income, "married_filing_jointly", 2026)
    assert result.taxable_social_security == 0.0
    assert result.federal_tax_owed == 1_000.0  # 10,000 @ 10%


def test_federal_tax_spans_multiple_brackets_mfj():
    """Higher income: taxable income (ordinary + taxable SS) crosses three
    bracket edges — a flat/blended shortcut would not reproduce this."""
    income = IncomeComponents(ordinary_income=150_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(income, "married_filing_jointly", 2026)
    assert result.taxable_social_security == 17_000.0
    # 24,800 @ 10% + 76,000 @ 12% + 66,200 @ 22% (2026 MFJ brackets)
    assert result.federal_tax_owed == 26_164.0


def test_federal_tax_single_filer_uses_single_bracket_table():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, "single", 2026)
    # 12,400 @ 10% + 38,000 @ 12% + 9,600 @ 22% (2026 single brackets)
    assert result.federal_tax_owed == 7_912.0


def test_federal_tax_figures_used_includes_both_ss_thresholds_and_brackets():
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(income, "married_filing_jointly", 2026)
    figure_names = {f.name for f in result.figures_used}
    assert "ss_provisional_income_thresholds_mfj" in figure_names
    assert "federal_brackets_mfj" in figure_names


def test_federal_tax_zero_income_owes_nothing():
    income = IncomeComponents(ordinary_income=0, social_security_gross_benefit=0)
    result = compute_federal_tax(income, "married_filing_jointly", 2026)
    assert result.federal_tax_owed == 0.0


def test_federal_brackets_are_verified_against_rev_proc_2025_32():
    """014-figure-verification (rp-9wi.1): both bracket tables are IRS
    Rev. Proc. 2025-32's actual tax year 2026 figures."""
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, "married_filing_jointly", 2026)
    bracket_figure = next(f for f in result.figures_used if f.name == "federal_brackets_mfj")
    assert bracket_figure.verified is True
    assert "Rev. Proc. 2025-32" in bracket_figure.citation
