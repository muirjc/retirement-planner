"""Roth conversion five-year seasoning (conversion-ladder) tracking
(019-roth-conversion-ladder, rp-886).

Deliberately a sibling module to roth_conversion.py, not a branch inside
compute_roth_conversion() -- that function's signature is a locked
contract (003's/010's contracts/mechanics-api.md) already consumed by
every conversion call site, and this module's own computation ("given a
draw amount and a list of prior conversions, how is that draw apportioned,
and does it touch unseasoned principal") has no dependency on
compute_roth_conversion()'s own internals (research.md Decision 1) --
mirrors 012-inherited-ira-rmd's own inherited_rmd.py-alongside-rmd.py
precedent.

compute_roth_ladder_consumption() is a pure, side-effect-free computation
over its explicit arguments, matching every other function in this
package (012's own contracts/mechanics-api.md: "every function in this
package remains a pure, side-effect-free computation over its explicit
arguments") -- it never mutates the `lots` list it is called with; it
returns a fresh, updated list instead (research.md Decision 5). The
caller (comparison.run_plan_projection()) maintains its own local list of
RothConversionLot instances and reassigns it to that updated list each
plan year -- see contracts/comparison-api.md for exactly how and where.

See specs/019-roth-conversion-ladder/contracts/mechanics-api.md for the
locked public shape.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from retirement_planner.tax import SourcedFigure

from .models import RothConversionLot, RothLadderConsumptionResult

_DOCUMENTED_YEARS = range(2020, 2075)

ROTH_CONVERSION_SEASONING_YEARS: SourcedFigure[int] = SourcedFigure(
    name="roth_conversion_seasoning_years",
    schedule={year: 5 for year in _DOCUMENTED_YEARS},
    citation=(
        "26 U.S.C. §408A(d)(3)(F) (a converted amount is treated, for early-distribution-tax "
        "purposes, as if it had always been a regular contribution once 5 tax years have elapsed "
        "from the tax year of conversion); Treas. Reg. §1.408A-6, Q&A-5 (applying this separately "
        "to each conversion, its own 5-year period running from January 1 of the conversion's own "
        "tax year)"
    ),
    last_verified=date(2026, 9, 1),
    verified=True,
)
"""Fixed by statute, not annually revised -- the schedule below repeats
the same 5-year period across _DOCUMENTED_YEARS, mirroring this
project's existing "fixed since enactment" figures (e.g.
tax/social_security.py's provisional-income thresholds,
mechanics/rmd.py's RMD_START_AGE pre-2033 step)."""


def compute_roth_ladder_consumption(
    lots: list[RothConversionLot],
    non_lot_roth_balance: float,
    roth_draw_amount: float,
    tax_year: int,
    age_condition_active: bool,
) -> RothLadderConsumptionResult:
    """Attributes roth_draw_amount across non_lot_roth_balance first (no
    limit beyond what's available there, never flagged -- this is the
    household's pre-existing/assumed-already-seasoned balance, FR-002),
    then across `lots` in order from the oldest conversion_tax_year to
    the newest, never drawing from a newer lot while an older one still
    has a positive balance (FR-004).

    A lot is "seasoned" once tax_year - lot.conversion_tax_year >=
    ROTH_CONVERSION_SEASONING_YEARS.value_for_year(tax_year) (FR-003).
    unseasoned_amount_flagged is the sum of every dollar drawn from a
    not-yet-seasoned lot this call, but ONLY when age_condition_active is
    True (FR-005/FR-006) -- otherwise 0.0 even if an unseasoned lot was
    drawn from.

    Pure: never mutates `lots` itself (research.md Decision 5) --
    RothLadderConsumptionResult.updated_lots is a fresh list, structurally
    the same length and order as `lots`, with each consumed lot's own
    balance reduced (an untouched lot's own instance is reused unchanged).

    figures_used carries ROTH_CONVERSION_SEASONING_YEARS's usage whenever
    roth_draw_amount > non_lot_roth_balance (a lot's own seasoning was
    actually consulted this year), regardless of the resulting flag
    (research.md Decision 4) -- empty whenever the draw never reaches a
    lot at all.

    Raises UnsupportedTaxYearError if ROTH_CONVERSION_SEASONING_YEARS has
    no schedule entry for tax_year. Does not itself validate that
    roth_draw_amount does not exceed non_lot_roth_balance plus the sum of
    every lot's own balance -- callers are expected to pass a draw amount
    already bounded by compute_withdrawal_plan()'s own accounting.
    """
    seasoning_period = ROTH_CONVERSION_SEASONING_YEARS.value_for_year(tax_year)  # raises UnsupportedTaxYearError

    draw_into_lots = max(0.0, roth_draw_amount - non_lot_roth_balance)

    figures_used = []
    if draw_into_lots > 0:
        figures_used.append(ROTH_CONVERSION_SEASONING_YEARS.usage_for_year(tax_year))

    updated_lots = [replace(lot) for lot in lots]
    remaining_to_draw = draw_into_lots
    unseasoned_amount_flagged = 0.0

    for lot in sorted(updated_lots, key=lambda entry: entry.conversion_tax_year):
        if remaining_to_draw <= 0:
            break
        if lot.balance <= 0:
            continue

        draw_from_lot = min(lot.balance, remaining_to_draw)
        lot.balance -= draw_from_lot
        remaining_to_draw -= draw_from_lot

        is_seasoned = (tax_year - lot.conversion_tax_year) >= seasoning_period
        if not is_seasoned and age_condition_active:
            unseasoned_amount_flagged += draw_from_lot

    return RothLadderConsumptionResult(
        updated_lots=updated_lots,
        unseasoned_amount_flagged=unseasoned_amount_flagged,
        figures_used=figures_used,
    )
