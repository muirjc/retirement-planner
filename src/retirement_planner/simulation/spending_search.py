"""Sustainable-spending range search (rp-3g0).

Answers "what can this household actually afford to spend?" as a real,
simulation-backed search over run_simulation()'s own success_rate output --
not a formula. annual_spending_need is a plain top-level argument to
run_simulation() (never part of StrategyConfiguration), so searching it
means holding every other input fixed and re-running the engine at
different candidate spending levels.

Critical correctness requirement: every candidate in one search reuses the
SAME return_paths (never regenerates random paths per candidate) --
success_rate is then a deterministic, monotonically non-increasing
function of spending (higher spending can only reduce or hold the success
rate steady, never raise it, against one fixed set of market paths), which
is exactly what bisection needs to converge. The caller (services/bff)
generates return_paths once via generate_configured_return_paths() and
passes them in; this module has no scenario-loading or return-path-
generation concerns of its own, mirroring the mechanics/comparison/
simulation package chain's existing "pure calculator" discipline.

Deliberately a pure function over an already-resolved context, not a new
top-level run_simulation() variant -- reuses that function's exact
signature/semantics for every parameter except annual_spending_need
itself (searched) and candidate_label (generated internally per call).
"""

from __future__ import annotations

from dataclasses import dataclass

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
from retirement_planner.scenario import Household

from .models import ReturnPath, SurvivalCurve
from .monte_carlo import run_simulation

_DEFAULT_TOLERANCE = 0.02
"""Search stops once a candidate's success_rate is within this many
percentage points (as a fraction, e.g. 0.02 = 2 points) of the target --
tight enough to be a meaningful answer, loose enough that the search
converges in a bounded number of iterations against Monte Carlo's own
discrete (not continuous) success_rate output (path_count candidates each
either succeed or don't, so success_rate itself only takes
path_count + 1 distinct values -- a smaller tolerance than 1/path_count
could never be satisfied exactly)."""

_DEFAULT_MAX_BRACKET_EXPANSIONS = 10
_DEFAULT_MAX_BISECTION_ITERATIONS = 15
_MIN_BRACKET_SPENDING = 1_000.0
"""A degenerate anchor_spending of $0 (or near it) still needs a nonzero
starting point to double outward from."""


@dataclass
class SpendingSearchResult:
    """One target success rate's own converged (or exhausted) search
    outcome."""

    spending: float
    achieved_success_rate: float
    target_success_rate: float
    iterations_used: int
    bracket_exhausted: bool
    """True if the search never found a spending level whose success_rate
    dropped below the target within max_bracket_expansions doublings --
    `spending` is then the last (largest) bracket value tried, not a
    converged answer; the true sustainable level is at or above it. False
    for every normal convergence."""


@dataclass
class SustainableSpendingRangeResult:
    """The full range: two independent single-target searches sharing one
    return_paths set, plus the (possibly reduced, relative to a full
    precision run) path count they were computed against -- callers must
    surface this so the range is never presented as more precise than it
    is (constitution Principle I)."""

    conservative: SpendingSearchResult
    flexible: SpendingSearchResult
    path_count_used: int


def _success_rate_at(
    spending: float,
    *,
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_paths: list[ReturnPath],
    survival_curves: dict[str, SurvivalCurve] | None,
    inherited_accounts: list[InheritedAccountBalance],
    net_earned_income_against_spending: bool,
) -> float:
    """One run_simulation() call at a candidate spending level, returning
    only the figure the search needs. inherited_accounts is passed through
    unchanged (never pre-copied here) -- run_simulation() already treats
    its own inherited_accounts parameter as an unmutated base list, making
    its own fresh per-path copy before every path (monte_carlo.py's own
    module docstring); safe to call repeatedly with the same base list
    across every candidate in a search the same way comparison/compare.py's
    own compare_*() functions already reuse a caller-supplied base list
    across candidates."""
    run = run_simulation(
        household=household,
        accounts=accounts,
        traditional_ownership_shares=traditional_ownership_shares,
        annual_spending_need=spending,
        state=state,
        reference_tax_year=reference_tax_year,
        start_plan_year=start_plan_year,
        start_tax_year=start_tax_year,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_paths=return_paths,
        candidate_label=f"spending_search_{spending:.2f}",
        survival_curves=survival_curves,
        inherited_accounts=inherited_accounts,
        net_earned_income_against_spending=net_earned_income_against_spending,
    )
    return run.success_rate


def search_spending_for_target_success_rate(
    *,
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_paths: list[ReturnPath],
    anchor_spending: float,
    target_success_rate: float,
    survival_curves: dict[str, SurvivalCurve] | None = None,
    inherited_accounts: list[InheritedAccountBalance] = [],  # noqa: B006 -- see _success_rate_at()'s own docstring: never mutated as a list
    net_earned_income_against_spending: bool = False,
    tolerance: float = _DEFAULT_TOLERANCE,
    max_bracket_expansions: int = _DEFAULT_MAX_BRACKET_EXPANSIONS,
    max_bisection_iterations: int = _DEFAULT_MAX_BISECTION_ITERATIONS,
) -> SpendingSearchResult:
    """Finds the annual_spending_need whose success_rate (against this
    exact return_paths set) is within `tolerance` of target_success_rate.

    Bracket expansion: $0 spending always succeeds on every path
    (annual_spending_need=0 can never produce a shortfall --
    compute_withdrawal_plan()'s own shortfall is only ever positive when a
    real need exceeds available balances/income), so success_rate(0.0) is
    always exactly 1.0 -- a universally valid lower bracket bound, never
    computed via an extra run_simulation() call. Starting from
    max(anchor_spending, _MIN_BRACKET_SPENDING), doubles the upper bound
    (moving the lower bound up to the previous upper bound each time, since
    its own success_rate is now known to be >= target) until a candidate's
    success_rate first drops below target_success_rate, or
    max_bracket_expansions is reached.

    Bisection: standard midpoint search on [low, high] where
    success_rate(low) >= target > success_rate(high) (or, if bracket
    expansion never found such a high, on the exhausted bracket instead --
    see bracket_exhausted below), narrowing until a candidate's
    success_rate is within tolerance of target_success_rate or
    max_bisection_iterations is reached -- whichever comes first. Returns
    the best (closest-to-target, and never above the target by more than
    one bisection step) candidate found, not necessarily an exact match --
    Monte Carlo's own success_rate is a discrete function of path_count
    candidates, so an exact match is not always possible (see
    _DEFAULT_TOLERANCE's own docstring).

    bracket_exhausted=True means max_bracket_expansions was reached while
    every doubled candidate's success_rate was STILL >= target_success_rate
    -- an unusually affordable household for this target, or a target set
    too low to be a meaningful ceiling. `spending`/`achieved_success_rate`
    then describe the last (largest) bracket candidate tried, not a
    converged answer -- the caller should present this as "still
    sustainable well above $X", not as a precise figure.
    """
    def rate_at(spending: float) -> float:
        """Closure over every fixed input -- avoids re-threading the same
        dozen keyword arguments through every _success_rate_at() call
        below, the only thing that varies across a search is `spending`
        itself."""
        return _success_rate_at(
            spending,
            household=household,
            accounts=accounts,
            traditional_ownership_shares=traditional_ownership_shares,
            state=state,
            reference_tax_year=reference_tax_year,
            start_plan_year=start_plan_year,
            start_tax_year=start_tax_year,
            plan_to_age=plan_to_age,
            strategy=strategy,
            return_paths=return_paths,
            survival_curves=survival_curves,
            inherited_accounts=inherited_accounts,
            net_earned_income_against_spending=net_earned_income_against_spending,
        )

    iterations = 0
    low, low_rate = 0.0, 1.0
    high = max(anchor_spending, _MIN_BRACKET_SPENDING)
    high_rate = rate_at(high)
    iterations += 1

    bracket_exhausted = False
    expansions = 0
    while high_rate >= target_success_rate:
        if expansions >= max_bracket_expansions:
            bracket_exhausted = True
            break
        low, low_rate = high, high_rate
        high *= 2.0
        high_rate = rate_at(high)
        iterations += 1
        expansions += 1

    if bracket_exhausted:
        return SpendingSearchResult(
            spending=high,
            achieved_success_rate=high_rate,
            target_success_rate=target_success_rate,
            iterations_used=iterations,
            bracket_exhausted=True,
        )

    # Invariant here: success_rate(low) >= target_success_rate > success_rate(high).
    best_spending, best_rate = low, low_rate
    for _ in range(max_bisection_iterations):
        mid = (low + high) / 2.0
        mid_rate = rate_at(mid)
        iterations += 1
        if mid_rate >= target_success_rate:
            low, low_rate = mid, mid_rate
            best_spending, best_rate = mid, mid_rate
        else:
            high, high_rate = mid, mid_rate
        if abs(best_rate - target_success_rate) <= tolerance:
            break

    return SpendingSearchResult(
        spending=best_spending,
        achieved_success_rate=best_rate,
        target_success_rate=target_success_rate,
        iterations_used=iterations,
        bracket_exhausted=False,
    )


def find_sustainable_spending_range(
    *,
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_paths: list[ReturnPath],
    anchor_spending: float,
    conservative_target_success_rate: float = 0.95,
    flexible_target_success_rate: float = 0.75,
    survival_curves: dict[str, SurvivalCurve] | None = None,
    inherited_accounts: list[InheritedAccountBalance] = [],  # noqa: B006 -- see _success_rate_at()'s own docstring
    net_earned_income_against_spending: bool = False,
) -> SustainableSpendingRangeResult:
    """The "range" a user actually wants: two independent
    search_spending_for_target_success_rate() calls sharing this exact
    return_paths set -- the "flexible" (lower success-rate target, higher
    affordable spending) and "conservative" (higher target, lower
    spending) ends. Defaults (95% / 75%) match common CFP-tool convention
    for a "safe" vs. "flexible" spending band; both are plain keyword
    arguments, not hardcoded, so a caller can offer a different pair."""
    conservative = search_spending_for_target_success_rate(
        household=household,
        accounts=accounts,
        traditional_ownership_shares=traditional_ownership_shares,
        state=state,
        reference_tax_year=reference_tax_year,
        start_plan_year=start_plan_year,
        start_tax_year=start_tax_year,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_paths=return_paths,
        anchor_spending=anchor_spending,
        target_success_rate=conservative_target_success_rate,
        survival_curves=survival_curves,
        inherited_accounts=inherited_accounts,
        net_earned_income_against_spending=net_earned_income_against_spending,
    )
    flexible = search_spending_for_target_success_rate(
        household=household,
        accounts=accounts,
        traditional_ownership_shares=traditional_ownership_shares,
        state=state,
        reference_tax_year=reference_tax_year,
        start_plan_year=start_plan_year,
        start_tax_year=start_tax_year,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_paths=return_paths,
        anchor_spending=anchor_spending,
        target_success_rate=flexible_target_success_rate,
        survival_curves=survival_curves,
        inherited_accounts=inherited_accounts,
        net_earned_income_against_spending=net_earned_income_against_spending,
    )
    return SustainableSpendingRangeResult(
        conservative=conservative,
        flexible=flexible,
        path_count_used=len(return_paths),
    )
