"""Unit tests for retirement_planner.tax.bracket_math (rp-bm8.3).

apply_progressive_brackets() is exercised extensively already, indirectly,
by test_federal.py and each state's own test file -- these tests cover
apply_progressive_brackets_detailed() directly: its per-bracket breakdown
sums to the same total apply_progressive_brackets() returns (guaranteed by
construction -- one wraps the other -- but asserted here too), and the
breakdown itself is correct row-by-row.
"""

from retirement_planner.tax.bracket_math import apply_progressive_brackets, apply_progressive_brackets_detailed
from retirement_planner.tax.models import BracketRow

_MFJ_2026_BRACKETS = (
    BracketRow(rate=0.10, income_up_to=24_800.0),
    BracketRow(rate=0.12, income_up_to=100_800.0),
    BracketRow(rate=0.22, income_up_to=211_400.0),
    BracketRow(rate=0.24, income_up_to=403_550.0),
    BracketRow(rate=0.32, income_up_to=512_450.0),
    BracketRow(rate=0.35, income_up_to=768_700.0),
    BracketRow(rate=0.37, income_up_to=None),
)


def test_detailed_and_summed_totals_agree_on_the_multi_bracket_worked_example():
    """Matches test_federal.py's own $134,800 taxable -> $19,080 owed
    worked example exactly."""
    total = apply_progressive_brackets(134_800.0, _MFJ_2026_BRACKETS)
    detailed_total, rows = apply_progressive_brackets_detailed(134_800.0, _MFJ_2026_BRACKETS)

    assert total == 19_080.0
    assert detailed_total == total
    assert sum(row.tax_in_bracket for row in rows) == total
    assert [(row.rate, row.income_in_bracket, row.tax_in_bracket) for row in rows] == [
        (0.10, 24_800.0, 2_480.0),
        (0.12, 76_000.0, 9_120.0),
        (0.22, 34_000.0, 7_480.0),
    ]


def test_detailed_breakdown_omits_brackets_never_reached():
    """Income entirely within the first bracket -> exactly one row, not
    seven (one per bracket in the table)."""
    total, rows = apply_progressive_brackets_detailed(10_000.0, _MFJ_2026_BRACKETS)

    assert total == 1_000.0
    assert len(rows) == 1
    assert (rows[0].rate, rows[0].income_in_bracket, rows[0].tax_in_bracket) == (0.10, 10_000.0, 1_000.0)


def test_detailed_breakdown_includes_the_top_unbounded_bracket():
    total, rows = apply_progressive_brackets_detailed(1_000_000.0, _MFJ_2026_BRACKETS)

    assert rows[-1].rate == 0.37
    assert rows[-1].income_in_bracket == 1_000_000.0 - 768_700.0
    assert sum(row.tax_in_bracket for row in rows) == total


def test_zero_or_negative_taxable_income_returns_empty_breakdown():
    assert apply_progressive_brackets_detailed(0.0, _MFJ_2026_BRACKETS) == (0.0, [])
    assert apply_progressive_brackets_detailed(-500.0, _MFJ_2026_BRACKETS) == (0.0, [])
