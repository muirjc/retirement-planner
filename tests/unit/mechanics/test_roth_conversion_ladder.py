"""Unit tests for compute_roth_ladder_consumption()
(019-roth-conversion-ladder, rp-886, US1/US2).

ROTH_CONVERSION_SEASONING_YEARS (5 years) is cross-checked directly against
26 U.S.C. §408A(d)(3)(F) and Treas. Reg. §1.408A-6, Q&A-5
(roth_conversion_ladder.py's own module docstring).
"""

import pytest

from retirement_planner.mechanics import (
    ROTH_CONVERSION_SEASONING_YEARS,
    RothConversionLot,
    compute_roth_ladder_consumption,
)
from retirement_planner.tax import UnsupportedTaxYearError

# --- US1: single-lot flag behavior ---


def test_draw_within_non_lot_balance_never_flags_regardless_of_lot_age():
    """spec.md Acceptance Scenario US1.4: a draw fully covered by the
    assumed-already-seasoned/pre-existing balance never touches a lot at
    all, so it's never flagged -- even an unseasoned lot, even with the
    age condition active."""
    lots = [RothConversionLot(conversion_tax_year=2026, balance=10_000.0)]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=50_000.0, roth_draw_amount=20_000.0, tax_year=2027, age_condition_active=True
    )
    assert result.unseasoned_amount_flagged == 0.0
    assert result.figures_used == []
    # The lot itself is untouched.
    assert result.updated_lots[0].balance == 10_000.0


def test_draw_into_unseasoned_lot_with_age_condition_active_flags_the_amount():
    """spec.md Acceptance Scenario US1.1: a draw reaching past the
    non-lot balance into a lot that hasn't cleared 5 tax years, while at
    least one household member is under 59.5, flags exactly the amount
    drawn from that lot."""
    lots = [RothConversionLot(conversion_tax_year=2026, balance=10_000.0)]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=5_000.0, roth_draw_amount=12_000.0, tax_year=2029, age_condition_active=True
    )
    # 2029 - 2026 = 3 years elapsed -- not yet seasoned (needs 5).
    assert result.unseasoned_amount_flagged == pytest.approx(7_000.0)  # 12,000 - 5,000 non-lot
    assert result.updated_lots[0].balance == pytest.approx(3_000.0)  # 10,000 - 7,000 drawn


def test_identical_draw_after_seasoning_never_flags():
    """spec.md Acceptance Scenario US1.2: the identical draw, once 5 full
    tax years have elapsed since the conversion, is never flagged."""
    lots = [RothConversionLot(conversion_tax_year=2026, balance=10_000.0)]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=5_000.0, roth_draw_amount=12_000.0, tax_year=2031, age_condition_active=True
    )
    # 2031 - 2026 = 5 years elapsed -- exactly seasoned.
    assert result.unseasoned_amount_flagged == 0.0


def test_identical_draw_with_age_condition_inactive_never_flags():
    """spec.md Acceptance Scenario US1.3: the identical draw into a
    still-unseasoned lot never flags once every household member has
    reached 60 (age_condition_active=False)."""
    lots = [RothConversionLot(conversion_tax_year=2026, balance=10_000.0)]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=5_000.0, roth_draw_amount=12_000.0, tax_year=2029, age_condition_active=False
    )
    assert result.unseasoned_amount_flagged == 0.0
    # The lot is still drawn down -- the age condition only gates the flag, not the draw itself.
    assert result.updated_lots[0].balance == pytest.approx(3_000.0)


def test_figures_used_populated_only_when_a_lot_is_actually_consulted():
    """research.md Decision 4: figures_used carries the seasoning
    figure's usage whenever the draw reaches into a lot at all --
    independent of whether the resulting flag ends up 0.0 (already
    seasoned, or age condition inactive)."""
    lots = [RothConversionLot(conversion_tax_year=2026, balance=10_000.0)]

    # Reaches into the lot, but already seasoned -- figure still consulted.
    seasoned_result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=0.0, roth_draw_amount=1_000.0, tax_year=2031, age_condition_active=True
    )
    assert len(seasoned_result.figures_used) == 1
    assert seasoned_result.figures_used[0].name == "roth_conversion_seasoning_years"

    # Never reaches the lot at all -- figure not consulted.
    untouched_result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=5_000.0, roth_draw_amount=1_000.0, tax_year=2029, age_condition_active=True
    )
    assert untouched_result.figures_used == []


def test_figures_used_carries_the_expected_citation_and_verified_flag():
    """spec.md FR-009, User Story 3: the figure cites its governing
    statute and carries a last_verified date, matching this project's
    existing regulated-figure convention."""
    lots = [RothConversionLot(conversion_tax_year=2026, balance=10_000.0)]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=0.0, roth_draw_amount=1_000.0, tax_year=2029, age_condition_active=True
    )
    usage = result.figures_used[0]
    assert usage.name == "roth_conversion_seasoning_years"
    assert "408A(d)(3)(F)" in usage.citation
    assert usage.verified is True
    assert usage.last_verified is not None


def test_unsupported_tax_year_raises():
    lots: list[RothConversionLot] = []
    with pytest.raises(UnsupportedTaxYearError):
        compute_roth_ladder_consumption(
            lots, non_lot_roth_balance=0.0, roth_draw_amount=0.0, tax_year=1999, age_condition_active=True
        )


def test_pure_never_mutates_the_lots_argument():
    """research.md Decision 5: the function must not mutate `lots` --
    every consumed lot's own balance change appears only in the returned
    updated_lots, never in the caller's original list/instances."""
    original_lot = RothConversionLot(conversion_tax_year=2026, balance=10_000.0)
    lots = [original_lot]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=0.0, roth_draw_amount=4_000.0, tax_year=2029, age_condition_active=True
    )
    assert original_lot.balance == 10_000.0  # untouched
    assert lots[0] is original_lot  # the caller's own list/instances are unchanged
    assert result.updated_lots[0].balance == pytest.approx(6_000.0)
    assert result.updated_lots[0] is not original_lot  # a fresh instance


def test_a_fully_drawn_down_lot_is_skipped():
    """spec.md Edge Cases: a lot whose balance has already reached 0.0
    contributes nothing further and is simply skipped, never flagged
    again."""
    lots = [
        RothConversionLot(conversion_tax_year=2026, balance=0.0),
        RothConversionLot(conversion_tax_year=2028, balance=5_000.0),
    ]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=0.0, roth_draw_amount=3_000.0, tax_year=2029, age_condition_active=True
    )
    assert result.updated_lots[0].balance == 0.0
    assert result.updated_lots[1].balance == pytest.approx(2_000.0)
    assert result.unseasoned_amount_flagged == pytest.approx(3_000.0)  # sourced from the second lot


# --- US2: multi-lot ordering ---


def test_partial_draw_sources_from_the_older_lot_first():
    """spec.md Acceptance Scenario US2.1: two unseasoned lots ($20,000 at
    year Y, $15,000 at year Y+2) -- a $10,000 draw past non_lot_roth_balance
    is sourced entirely from the older (Y) lot, leaving Y+2 untouched."""
    lots = [
        RothConversionLot(conversion_tax_year=2026, balance=20_000.0),
        RothConversionLot(conversion_tax_year=2028, balance=15_000.0),
    ]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=0.0, roth_draw_amount=10_000.0, tax_year=2029, age_condition_active=True
    )
    assert result.updated_lots[0].balance == pytest.approx(10_000.0)  # 20,000 - 10,000
    assert result.updated_lots[1].balance == pytest.approx(15_000.0)  # untouched
    assert result.unseasoned_amount_flagged == pytest.approx(10_000.0)


def test_draw_exhausting_the_older_lot_spills_into_the_newer_one():
    """spec.md Acceptance Scenario US2.2: a $25,000 draw exhausts the
    $20,000 Y lot first, then draws the remaining $5,000 from the Y+2
    lot."""
    lots = [
        RothConversionLot(conversion_tax_year=2026, balance=20_000.0),
        RothConversionLot(conversion_tax_year=2028, balance=15_000.0),
    ]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=0.0, roth_draw_amount=25_000.0, tax_year=2029, age_condition_active=True
    )
    assert result.updated_lots[0].balance == 0.0
    assert result.updated_lots[1].balance == pytest.approx(10_000.0)  # 15,000 - 5,000
    assert result.unseasoned_amount_flagged == pytest.approx(25_000.0)  # both lots still unseasoned


def test_only_the_still_unseasoned_lots_portion_of_a_mixed_draw_is_flagged():
    """spec.md Acceptance Scenario US2.3: the Y lot has since seasoned
    but Y+2 has not -- only the portion of a draw sourced from Y+2 is
    flagged; the portion within the now-seasoned Y lot's amount is not."""
    lots = [
        RothConversionLot(conversion_tax_year=2026, balance=20_000.0),  # seasoned by 2031 (5 years)
        RothConversionLot(conversion_tax_year=2028, balance=15_000.0),  # not seasoned until 2033
    ]
    result = compute_roth_ladder_consumption(
        lots, non_lot_roth_balance=0.0, roth_draw_amount=25_000.0, tax_year=2031, age_condition_active=True
    )
    assert result.updated_lots[0].balance == 0.0  # Y lot fully drawn (seasoned, no flag)
    assert result.updated_lots[1].balance == pytest.approx(10_000.0)  # Y+2 lot drawn $5,000 (unseasoned, flagged)
    assert result.unseasoned_amount_flagged == pytest.approx(5_000.0)
