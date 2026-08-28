"""Withdrawal sequencing (FR-004–FR-007).

Modeled as named, swappable account-type orderings (data, rather than one
callable per strategy) since every sequencing strategy performs identical
arithmetic and differs only in draw order — see
specs/003-retirement-account-mechanics/research.md §5 and plan.md's
Constitution Check for the rationale.

See specs/003-retirement-account-mechanics/contracts/mechanics-api.md
("Operations (withdrawal_sequencing)" section) for the locked public shape.
"""

from __future__ import annotations

from dataclasses import replace

from .models import AccountBalances, AccountType, WithdrawalLineItem, WithdrawalPlan

WITHDRAWAL_STRATEGIES: dict[str, tuple[AccountType, ...]] = {
    "rmd_taxable_traditional_roth": ("taxable", "traditional", "roth"),
    # Added by 004-strategy-comparison-layer (research.md §8) so a
    # withdrawal-order comparison has a second, genuinely different order
    # to compare against the default above.
    "rmd_traditional_taxable_roth": ("traditional", "taxable", "roth"),
}
"""Registry mapping a strategy name to the non-RMD account-type draw order
(FR-005). Adding a new strategy means adding one tuple + one registry entry
here — nothing else in this package changes (SC-006).
"""


def compute_withdrawal_plan(
    spending_need: float,
    rmd_amount: float,
    starting_balances: AccountBalances,
    strategy: str = "rmd_taxable_traditional_roth",
) -> WithdrawalPlan:
    """Draws rmd_amount from starting_balances.traditional first (FR-004),
    unconditionally — this leg is not part of the configured ordering. If
    spending_need is already met by rmd_amount, no further draws occur.
    Otherwise draws the remaining need from account types in the order
    WITHDRAWAL_STRATEGIES[strategy] specifies, never exceeding an account's
    available balance (FR-006); once an account type is exhausted, the
    unmet remainder moves to the next type in the sequence. If total
    available balance across all account types (including rmd_amount's
    traditional draw) is less than spending_need, the unmet amount is
    reported as shortfall and no balance goes negative (FR-007). Raises
    KeyError if strategy has no registered ordering.
    """
    order = WITHDRAWAL_STRATEGIES[strategy]  # raises KeyError

    ending_balances = replace(starting_balances)
    rmd_drawn = min(rmd_amount, ending_balances.traditional)
    ending_balances.traditional -= rmd_drawn

    remaining_need = spending_need - rmd_drawn
    sequence_withdrawals: list[WithdrawalLineItem] = []

    for account_type in order:
        if remaining_need <= 0:
            break
        available = getattr(ending_balances, account_type)
        draw = min(available, remaining_need)
        if draw > 0:
            sequence_withdrawals.append(WithdrawalLineItem(account_type=account_type, amount=draw))
            setattr(ending_balances, account_type, available - draw)
            remaining_need -= draw

    shortfall = max(0.0, remaining_need)

    return WithdrawalPlan(
        rmd_drawn=rmd_drawn,
        sequence_withdrawals=sequence_withdrawals,
        ending_balances=ending_balances,
        shortfall=shortfall,
    )
