"""Unit tests for resolve_cash_reserve_draw()/resolve_cash_reserve_refill()
(rp-e0h)."""

from retirement_planner.mechanics import resolve_cash_reserve_draw, resolve_cash_reserve_refill


# --- resolve_cash_reserve_draw() ---


def test_down_year_draws_up_to_spending_need_from_cash():
    drawn, remaining = resolve_cash_reserve_draw(spending_need=50_000, cash_balance=200_000, is_down_year=True)
    assert drawn == 50_000
    assert remaining == 0.0


def test_down_year_draw_capped_by_available_cash_leaving_a_remainder():
    drawn, remaining = resolve_cash_reserve_draw(spending_need=50_000, cash_balance=30_000, is_down_year=True)
    assert drawn == 30_000
    assert remaining == 20_000


def test_up_year_draws_nothing_from_cash():
    drawn, remaining = resolve_cash_reserve_draw(spending_need=50_000, cash_balance=200_000, is_down_year=False)
    assert drawn == 0.0
    assert remaining == 50_000


def test_down_year_with_empty_cash_draws_nothing():
    drawn, remaining = resolve_cash_reserve_draw(spending_need=50_000, cash_balance=0.0, is_down_year=True)
    assert drawn == 0.0
    assert remaining == 50_000


def test_down_year_with_zero_spending_need_draws_nothing():
    drawn, remaining = resolve_cash_reserve_draw(spending_need=0.0, cash_balance=200_000, is_down_year=True)
    assert drawn == 0.0
    assert remaining == 0.0


# --- resolve_cash_reserve_refill() ---


def test_up_year_refills_up_to_the_target():
    refilled = resolve_cash_reserve_refill(cash_target=300_000, current_cash_balance=100_000, available_taxable_balance=500_000, is_down_year=False)
    assert refilled == 200_000


def test_up_year_refill_capped_by_available_taxable():
    refilled = resolve_cash_reserve_refill(cash_target=300_000, current_cash_balance=100_000, available_taxable_balance=50_000, is_down_year=False)
    assert refilled == 50_000


def test_down_year_never_refills_even_if_below_target():
    refilled = resolve_cash_reserve_refill(cash_target=300_000, current_cash_balance=50_000, available_taxable_balance=500_000, is_down_year=True)
    assert refilled == 0.0


def test_already_at_or_above_target_refills_nothing():
    refilled = resolve_cash_reserve_refill(cash_target=300_000, current_cash_balance=300_000, available_taxable_balance=500_000, is_down_year=False)
    assert refilled == 0.0

    above_target = resolve_cash_reserve_refill(cash_target=300_000, current_cash_balance=350_000, available_taxable_balance=500_000, is_down_year=False)
    assert above_target == 0.0


def test_refill_never_exceeds_a_negative_or_zero_taxable_balance():
    refilled = resolve_cash_reserve_refill(cash_target=300_000, current_cash_balance=100_000, available_taxable_balance=0.0, is_down_year=False)
    assert refilled == 0.0
