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


def test_omitted_inherited_distribution_amount_reproduces_prior_behavior():
    # 012-inherited-ira-rmd (research.md §10): defaulting to 0.0 must be a
    # strict no-op -- identical to every call above that never passes it.
    balances = AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)
    plan = compute_withdrawal_plan(spending_need=80_000, rmd_amount=40_000, starting_balances=balances)
    assert plan.inherited_distribution_drawn == 0.0


def test_inherited_distribution_amount_reduces_remaining_need_like_rmd_drawn():
    # 012-inherited-ira-rmd: an inherited account's distribution funds
    # spending_need "first, unconditionally" exactly like rmd_amount, but
    # is never subtracted from starting_balances.traditional -- it was
    # never part of that pooled balance (research.md §10).
    balances = AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)
    plan = compute_withdrawal_plan(
        spending_need=80_000,
        rmd_amount=40_000,
        starting_balances=balances,
        inherited_distribution_amount=30_000,
    )
    assert plan.inherited_distribution_drawn == 30_000
    assert plan.rmd_drawn == 40_000
    assert plan.ending_balances.traditional == 500_000 - 40_000  # unaffected by inherited_distribution_amount
    # remaining_need = 80,000 - 40,000 (rmd) - 30,000 (inherited) = 10,000
    assert sum(item.amount for item in plan.sequence_withdrawals) == pytest.approx(10_000)


def test_inherited_distribution_amount_never_capped_by_this_functions_own_logic():
    # The caller has already confirmed the amount doesn't exceed the
    # source inherited account's own balance before calling this function
    # -- compute_withdrawal_plan() itself applies no cap (mechanics-api.md).
    balances = AccountBalances(traditional=0, roth=0, taxable=0)
    plan = compute_withdrawal_plan(
        spending_need=10_000,
        rmd_amount=0,
        starting_balances=balances,
        inherited_distribution_amount=250_000,
    )
    assert plan.inherited_distribution_drawn == 250_000
    assert plan.shortfall == 0.0
