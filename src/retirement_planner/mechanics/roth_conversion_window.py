"""Auto-derived ("gap-year") Roth conversion window (rp-nui).

Deliberately a sibling module to roth_conversion.py, not a branch inside
compute_roth_conversion() -- that function's signature is a locked contract
(003's contracts/mechanics-api.md) already consumed by every conversion
call site, and this module's own computation ("given a household's ages
and wage-income end dates, what calendar-year window should
fill_to_bracket_ceiling() run in") has no dependency on
compute_roth_conversion()'s own internals -- mirrors
roth_conversion_ladder.py's own sibling-module precedent.

Implements the CFP "Roth conversion window" / "tax bracket management"
practice (Kitces et al.): the years between a household's wages stopping
and its members' RMDs starting are a low-income window worth filling with
Roth conversions, shrinking the eventual mandatory RMD and smoothing
lifetime tax brackets. RMDs themselves are never delayable (26 U.S.C.
§401(a)(9); a 25% excise tax applies to any shortfall) -- this module never
attempts that. It only widens or narrows the *window in which the engine's
existing, unmodified bracket-fill strategy is allowed to run* -- the
conversion amount each year is still sized entirely by
fill_to_bracket_ceiling() (roth_conversion.py), untouched by this module.

resolve_gap_window() is a pure, side-effect-free computation over its
explicit arguments, matching every other function in this package. See
docs/BRD.md §6.6b for the narrative rationale and its cross-link to the
rp-8la/rp-8mw single-pass Social-Security-taxability simplification this
feature's target population (an early-retirement Roth-conversion-bridge
household) most directly interacts with.
"""

from __future__ import annotations

from retirement_planner.tax import FigureUsage

from .models import GapWindowMemberInputs
from .rmd import RMD_START_AGE, first_rmd_tax_year


def resolve_gap_window(
    members: list[GapWindowMemberInputs],
    reference_tax_year: int,
) -> tuple[tuple[int, int] | None, list[FigureUsage]]:
    """The household-level auto Roth-conversion window. Conversions in this
    engine execute against pooled, household-level AccountBalances (never
    per-member) -- compute_plan_year_mechanics()/run_plan_projection() --
    so this always resolves to one household-level (start, end) tuple, not
    a per-member window.

    Rule (a documented decision -- see module docstring -- not to be
    silently changed by future work without a new decision record):

    window_start = 1 + max over members of that member's own last active-
    wage tax year (reference_tax_year + (latest_wage_end_age -
    current_age)) -- the FIRST tax year in which EVERY member's wages have
    stopped, not the earliest member's own stop year. Opening the window
    before every wage-earner has stopped would layer conversions on top of
    active wages -- both are pooled into the same
    ordinary_income_established total fill_to_bracket_ceiling() sizes
    against -- the wage-stacking guard, the opposite of what the
    low-income-window strategy targets.

    window_end = (earliest tax year, across ALL members regardless of that
    member's own traditional-ownership share, in which that member first
    becomes RMD-eligible via mechanics.rmd.first_rmd_tax_year()) minus 1.
    Uses the EARLIEST member -- conservative, erring toward closing the
    window early rather than late. Deliberately does NOT consult
    traditional_ownership_shares (a comparison-layer concept, unavailable
    to this mechanics-layer pure function) -- a member who owns 0% of the
    household's traditional balance still closes the window at their own
    RMD-eligibility age. A documented simplification, not a strict
    optimum.

    Returns (None, []) -- degrading to "no conversions ever" via
    compute_roth_conversion()'s own existing window=None no-op path -- when
    window_start > window_end (no chronological gap exists for this
    household's actual ages), when `members` is empty, or when any
    member's latest_wage_end_age is None (wages structurally never stop
    for at least one member).

    rp-8la/rp-8mw cross-link: a household this rule targets -- wages just
    stopped, Social Security not yet claimed -- is exactly the population
    docs/BRD.md §6.6's single-pass Social-Security-taxability note flags as
    its worst case (pre-conversion provisional income below threshold_2,
    so a sized conversion can cross a taxability tier the single pass
    never re-solves against). This function does not fix that
    simplification -- out of scope, a settled decision -- it exists so the
    interaction is explicit in code, not silently compounded.

    Raises UnsupportedTaxYearError (via first_rmd_tax_year()) if
    reference_tax_year, or a member's own eventual RMD-eligibility year, is
    outside RMD_START_AGE's documented schedule.
    """
    if not members or any(member.latest_wage_end_age is None for member in members):
        return None, []

    wage_end_tax_years = []
    for member in members:
        # The `any(... is None ...)` check above already guarantees this,
        # but mypy can't track that guarantee across a separate loop --
        # this assert narrows int | None -> int the same way rmd.py's own
        # `assert spouse_age is not None` narrows a sibling optional field.
        assert member.latest_wage_end_age is not None
        wage_end_tax_years.append(reference_tax_year + (member.latest_wage_end_age - member.current_age))
    window_start = 1 + max(wage_end_tax_years)

    rmd_eligible_years = [first_rmd_tax_year(member.current_age, reference_tax_year) for member in members]
    earliest_rmd_eligible_year = min(rmd_eligible_years)
    window_end = earliest_rmd_eligible_year - 1
    # The earliest member's own RMD-eligible year is the one that actually
    # determined window_end -- one FigureUsage citing RMD_START_AGE for
    # that year, not one per member (every member's own RMD_START_AGE
    # lookup used the same underlying schedule, and only this one value
    # is load-bearing to the returned window).
    figures_used = [RMD_START_AGE.usage_for_year(earliest_rmd_eligible_year)]

    if window_start > window_end:
        return None, figures_used

    return (window_start, window_end), figures_used
