"""Unit tests for compute_federal_tax() (US1).

Expected tax amounts are hand-calculated against federal.py's actual IRS
Rev. Proc. 2025-32 tax year 2026 bracket and standard-deduction figures
(014-figure-verification, rp-9wi.1; rp-7me) — what's under test here is
that the *math* (standard deduction + progressive brackets + real SS
taxability) is genuine, not merely that these specific numbers are
IRS-official (they now are).
"""

from retirement_planner.tax import IncomeComponents
from retirement_planner.tax.federal import compute_federal_tax


def test_federal_tax_is_genuine_progressive_bracket_math_mfj():
    """Taxable income (after the $32,200 MFJ standard deduction) stays
    entirely in the first bracket."""
    income = IncomeComponents(ordinary_income=40_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [40, 42], "married_filing_jointly", 2026)
    assert result.taxable_social_security == 0.0
    assert result.federal_tax_owed == 780.0  # (40,000 - 32,200) @ 10%


def test_federal_tax_spans_multiple_brackets_mfj():
    """Higher income: taxable income (ordinary + taxable SS - standard
    deduction) crosses three bracket edges — a flat/blended shortcut would
    not reproduce this. Ages under 65 isolate this from the age-65
    addition, covered separately below."""
    income = IncomeComponents(ordinary_income=150_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(income, [50, 52], "married_filing_jointly", 2026)
    assert result.taxable_social_security == 17_000.0
    # taxable = 150,000 + 17,000 - 32,200 = 134,800
    # 24,800 @ 10% + 76,000 @ 12% + 34,000 @ 22% (2026 MFJ brackets)
    assert result.federal_tax_owed == 19_080.0


def test_federal_tax_single_filer_uses_single_bracket_table():
    income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [50], "single", 2026)
    # taxable = 60,000 - 16,100 (single standard deduction) = 43,900
    # 12,400 @ 10% + 31,500 @ 12% (2026 single brackets)
    assert result.federal_tax_owed == 5_020.0


def test_federal_tax_figures_used_includes_ss_thresholds_brackets_and_standard_deduction():
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(income, [67, 65], "married_filing_jointly", 2026)
    figure_names = {f.name for f in result.figures_used}
    assert "ss_provisional_income_thresholds_mfj" in figure_names
    assert "federal_brackets_mfj" in figure_names
    assert "standard_deduction_mfj" in figure_names


def test_federal_tax_zero_income_owes_nothing():
    income = IncomeComponents(ordinary_income=0, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [67, 65], "married_filing_jointly", 2026)
    assert result.federal_tax_owed == 0.0


def test_federal_brackets_are_verified_against_rev_proc_2025_32():
    """014-figure-verification (rp-9wi.1): both bracket tables are IRS
    Rev. Proc. 2025-32's actual tax year 2026 figures."""
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [67, 65], "married_filing_jointly", 2026)
    bracket_figure = next(f for f in result.figures_used if f.name == "federal_brackets_mfj")
    assert bracket_figure.verified is True
    assert "Rev. Proc. 2025-32" in bracket_figure.citation


# ---------------------------------------------------------------------------
# rp-7me: standard deduction (previously missing entirely -- taxable income
# was ordinary income + taxable SS with nothing subtracted before bracket
# application, overstating federal tax owed in every scenario).
# ---------------------------------------------------------------------------


def test_standard_deduction_shields_income_below_it_entirely_mfj():
    income = IncomeComponents(ordinary_income=30_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [40, 42], "married_filing_jointly", 2026)
    assert result.federal_tax_owed == 0.0


def test_standard_deduction_shields_income_below_it_entirely_single():
    income = IncomeComponents(ordinary_income=15_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [40], "single", 2026)
    assert result.federal_tax_owed == 0.0


def test_standard_deduction_never_pushes_taxable_income_negative():
    """A deduction larger than income floors taxable income at $0, never
    produces a negative number (let alone a refund) from bracket math."""
    income = IncomeComponents(ordinary_income=1_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [70, 70], "married_filing_jointly", 2026)
    assert result.federal_tax_owed == 0.0


def test_age_65_addition_reduces_tax_owed_relative_to_under_65():
    """Same income, same filing status -- only ages differ. A household
    with a filer who has reached 65 gets a larger standard deduction
    (26 U.S.C. §63(f)) and so owes less."""
    income = IncomeComponents(ordinary_income=34_000, social_security_gross_benefit=0)
    under_65 = compute_federal_tax(income, [64, 64], "married_filing_jointly", 2026)
    one_at_65 = compute_federal_tax(income, [65, 64], "married_filing_jointly", 2026)

    assert under_65.federal_tax_owed == 180.0  # (34,000 - 32,200) @ 10%
    assert one_at_65.federal_tax_owed == 15.0  # (34,000 - 32,200 - 1,650) @ 10%
    assert one_at_65.federal_tax_owed < under_65.federal_tax_owed


def test_standard_deduction_figure_is_verified_against_rev_proc_2025_32():
    income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [67, 65], "married_filing_jointly", 2026)
    deduction_figure = next(f for f in result.figures_used if f.name == "standard_deduction_mfj")
    assert deduction_figure.verified is True
    assert "Rev. Proc. 2025-32" in deduction_figure.citation
