"""Cash-reserve ("bucket") withdrawal strategy (rp-e0h): in a down year,
draw spending from a household's own cash reserve first, leaving every
other account untouched; in an up year, refill the reserve from the
taxable account, up to its own target.

Deliberately tracked entirely outside compute_withdrawal_plan()/
WITHDRAWAL_STRATEGIES (withdrawal_sequencing.py) -- that module models a
STATIC account-type draw order (research.md §5: "every sequencing
strategy performs identical arithmetic and differs only in draw order"),
while this is a market-return-CONDITIONAL rule, a difference in kind, not
just order. The caller (comparison/projection.py) owns its own cash
balance as a plain float across the plan horizon, calling these two pure
functions once per plan year; neither function reads or mutates a real
AccountBalances instance.
"""

from __future__ import annotations


def resolve_cash_reserve_draw(spending_need: float, cash_balance: float, is_down_year: bool) -> tuple[float, float]:
    """Returns (cash_drawn, reduced_spending_need). A down year draws up
    to spending_need from cash_balance first; an up year draws nothing
    from cash for spending at all (cash_drawn=0.0, spending_need
    unchanged) -- the household's own configured withdrawal order covers
    an up year's spending exactly as it already does without this
    feature."""
    if not is_down_year or cash_balance <= 0.0 or spending_need <= 0.0:
        return 0.0, spending_need
    drawn = min(cash_balance, spending_need)
    return drawn, spending_need - drawn


def resolve_cash_reserve_refill(cash_target: float, current_cash_balance: float, available_taxable_balance: float, is_down_year: bool) -> float:
    """Returns the amount to move from taxable into cash this year. A
    down year never refills (0.0) -- the whole point of drawing from cash
    that year is to leave every other account alone, not immediately
    siphon taxable right back into cash the same year. Never exceeds
    available_taxable_balance (a refill never forces a shortfall), and
    never pulls from traditional/roth -- a cash reserve is refilled only
    from the liquid, non-tax-advantaged bucket, the same account type
    every existing withdrawal order already draws from first."""
    if is_down_year:
        return 0.0
    shortfall = cash_target - current_cash_balance
    if shortfall <= 0.0:
        return 0.0
    return min(shortfall, available_taxable_balance)
