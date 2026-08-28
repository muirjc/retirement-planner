"""Unit tests for compute_withdrawal_plan() (US2)."""

import pytest

from retirement_planner.mechanics import AccountBalances, compute_withdrawal_plan


def test_default_order_draws_rmd_then_taxable_then_traditional_then_roth():
    balances = AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)
    plan = compute_withdrawal_plan(spending_need=80_000, rmd_amount=40_000, starting_balances=balances)
    assert plan.rmd_drawn == 40_000
    assert plan.sequence_withdrawals[0].account_type == "taxable"
    assert plan.shortfall == 0


def test_rmd_alone_meeting_need_draws_nothing_further():
    balances = AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)
    plan = compute_withdrawal_plan(spending_need=30_000, rmd_amount=40_000, starting_balances=balances)
    assert plan.sequence_withdrawals == []


def test_remainder_rolls_to_next_account_once_current_is_exhausted():
    balances = AccountBalances(traditional=500_000, roth=200_000, taxable=10_000)
    plan = compute_withdrawal_plan(spending_need=80_000, rmd_amount=40_000, starting_balances=balances)
    account_types_drawn = [item.account_type for item in plan.sequence_withdrawals]
    assert account_types_drawn == ["taxable", "traditional"]
    assert plan.ending_balances.taxable == 0


def test_shortfall_reported_explicitly_never_negative_balance():
    balances = AccountBalances(traditional=0, roth=0, taxable=1_000)
    plan = compute_withdrawal_plan(spending_need=50_000, rmd_amount=0, starting_balances=balances)
    assert plan.shortfall == 49_000
    assert plan.ending_balances.taxable == 0
    assert plan.ending_balances.traditional == 0
    assert plan.ending_balances.roth == 0


def test_starting_balances_object_is_not_mutated_by_the_caller():
    balances = AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)
    compute_withdrawal_plan(spending_need=80_000, rmd_amount=40_000, starting_balances=balances)
    assert balances == AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)


def test_unregistered_strategy_raises_keyerror():
    balances = AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)
    with pytest.raises(KeyError):
        compute_withdrawal_plan(
            spending_need=80_000, rmd_amount=40_000, starting_balances=balances, strategy="nope"
        )


def test_traditional_taxable_roth_order_draws_traditional_before_taxable():
    # Added by 004-strategy-comparison-layer (research.md §8) so a
    # withdrawal-order comparison has a second genuinely different order.
    balances = AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)
    plan = compute_withdrawal_plan(
        spending_need=80_000,
        rmd_amount=40_000,
        starting_balances=balances,
        strategy="rmd_traditional_taxable_roth",
    )
    assert plan.rmd_drawn == 40_000
    assert plan.sequence_withdrawals[0].account_type == "traditional"
