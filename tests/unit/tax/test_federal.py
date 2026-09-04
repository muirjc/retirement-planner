"""Unit tests for compute_federal_tax() (US1).

Expected tax amounts are hand-calculated against federal.py's actual IRS
Rev. Proc. 2025-32 tax year 2026 bracket and standard-deduction figures
(014-figure-verification, rp-9wi.1; rp-7me) — what's under test here is
that the *math* (standard deduction + progressive brackets + real SS
taxability) is genuine, not merely that these specific numbers are
IRS-official (they now are).
"""

import pytest

from retirement_planner.tax import IncomeComponents, UnsupportedTaxYearError
from retirement_planner.tax.federal import bracket_ceiling_for_rate, compute_federal_tax


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


# -- rp-bm8.3: previously-discarded intermediate values, now retained --


def test_taxable_income_and_standard_deduction_used_are_retained_single_bracket():
    income = IncomeComponents(ordinary_income=40_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [40, 42], "married_filing_jointly", 2026)
    assert result.standard_deduction_used == 32_200.0
    assert result.taxable_income == 7_800.0  # 40,000 - 32,200
    assert len(result.bracket_breakdown) == 1
    row = result.bracket_breakdown[0]
    assert (row.rate, row.income_in_bracket, row.tax_in_bracket) == (0.10, 7_800.0, 780.0)


def test_bracket_breakdown_matches_the_multi_bracket_worked_example():
    """Same worked example test_federal_tax_spans_multiple_brackets_mfj()
    already covers ($134,800 taxable -> $19,080 owed) -- this asserts the
    per-bracket rows retained alongside that total (rp-bm8.3)."""
    income = IncomeComponents(ordinary_income=150_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(income, [50, 52], "married_filing_jointly", 2026)

    assert result.taxable_income == 134_800.0
    assert result.standard_deduction_used == 32_200.0
    rows = [(row.rate, row.income_in_bracket, row.tax_in_bracket) for row in result.bracket_breakdown]
    assert rows == [
        (0.10, 24_800.0, 2_480.0),
        (0.12, 76_000.0, 9_120.0),
        (0.22, 34_000.0, 7_480.0),
    ]
    assert sum(row.tax_in_bracket for row in result.bracket_breakdown) == result.federal_tax_owed


def test_bracket_breakdown_is_empty_when_taxable_income_is_zero():
    income = IncomeComponents(ordinary_income=1_000, social_security_gross_benefit=0)
    result = compute_federal_tax(income, [70, 70], "married_filing_jointly", 2026)
    assert result.taxable_income == 0.0
    assert result.bracket_breakdown == []


# -- rp-nui: bracket_ceiling_for_rate() -- the real dollar ceiling for a
# NAMED bracket rate, in the pre-standard-deduction basis
# fill_to_bracket_ceiling()'s own `ceiling` parameter is compared against.
# ---------------------------------------------------------------------------


def test_bracket_ceiling_for_rate_adds_back_the_standard_deduction_mfj():
    """The key architectural finding this function exists to handle:
    BracketRow.income_up_to is stated in compute_federal_tax()'s own
    POST-standard-deduction taxable_income basis, but
    fill_to_bracket_ceiling() compares its `ceiling` argument against a
    PRE-deduction established_taxable_income -- naively returning
    income_up_to alone would under-fill by exactly the deduction amount."""
    ceiling, _figures = bracket_ceiling_for_rate(0.22, "married_filing_jointly", 2026, [])
    assert ceiling == 243_600.0  # 211,400 (22% row's income_up_to) + 32,200 (MFJ standard deduction)


def test_bracket_ceiling_for_rate_single_filer():
    ceiling, _figures = bracket_ceiling_for_rate(0.12, "single", 2026, [])
    assert ceiling == 66_500.0  # 50,400 + 16,100 (single standard deduction)


def test_bracket_ceiling_for_rate_crosses_the_age_65_standard_deduction_addition():
    under_65_ceiling, _ = bracket_ceiling_for_rate(0.22, "married_filing_jointly", 2026, [60, 60])
    one_at_65_ceiling, _ = bracket_ceiling_for_rate(0.22, "married_filing_jointly", 2026, [65, 60])
    assert one_at_65_ceiling == under_65_ceiling + 1_650.0  # one filer's own age-65 addition


def test_bracket_ceiling_for_rate_raises_on_a_rate_with_no_exact_match():
    """No fuzzy/nearest-rate matching -- a mistyped rate fails loudly."""
    with pytest.raises(ValueError, match="0.23"):
        bracket_ceiling_for_rate(0.23, "married_filing_jointly", 2026, [])


def test_bracket_ceiling_for_rate_raises_on_the_unbounded_top_bracket():
    """37% is the top row (income_up_to=None) -- "ceiling of an unbounded
    bracket" is not a finite number."""
    with pytest.raises(ValueError, match="unbounded"):
        bracket_ceiling_for_rate(0.37, "married_filing_jointly", 2026, [])


def test_bracket_ceiling_for_rate_raises_unsupported_tax_year():
    with pytest.raises(UnsupportedTaxYearError):
        bracket_ceiling_for_rate(0.22, "married_filing_jointly", 1999, [])


def test_bracket_ceiling_for_rate_figures_used_includes_brackets_and_standard_deduction():
    _ceiling, figures = bracket_ceiling_for_rate(0.22, "married_filing_jointly", 2026, [])
    figure_names = {f.name for f in figures}
    assert figure_names == {"federal_brackets_mfj", "standard_deduction_mfj"}


def test_bracket_ceiling_for_rate_does_not_change_compute_federal_tax_behavior():
    """Regression for the _standard_deduction_for() extraction refactor --
    compute_federal_tax()'s own output is unaffected by factoring its
    standard-deduction computation out into a function shared with
    bracket_ceiling_for_rate()."""
    income = IncomeComponents(ordinary_income=150_000, social_security_gross_benefit=20_000)
    result = compute_federal_tax(income, [50, 52], "married_filing_jointly", 2026)
    assert result.federal_tax_owed == 19_080.0
    assert result.standard_deduction_used == 32_200.0
