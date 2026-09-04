"""Multi-path Monte Carlo simulation (FR-002-FR-004, FR-006, FR-017-FR-019):
runs run_plan_projection() once per ReturnPath, aggregating into a success
rate, percentile ending-balance bands, and (optionally) a survival-adjusted
success rate. Path-level work is dispatched across worker processes once
path_count exceeds a threshold (research.md §7). See
specs/005-simulation-engine/contracts/simulation-api.md.

death_year_draws (023-probabilistic-death-draws rp-vgv,
specs/023-probabilistic-death-draws/contracts/simulation-api.md): a second,
independent, opt-in capability alongside the survival_curves-driven
survival_adjusted_success_rate above -- that older metric is a post-hoc
threshold check that never touches what a path actually funds, run
identically for every path. This one instead lets each path draw its own
probabilistic death age per household member (simulation.mortality) and
fund/score that path AS that death, via a per-path Household override
(_household_for_path()) -- reusing 018's existing survivor-scenario
projection logic completely unchanged. The two coexist without changing
each other's own computation; neither is a replacement for the other.

inherited_accounts (012-inherited-ira-rmd rp-mt7, research.md §10 addendum):
run_plan_projection() mutates each InheritedAccountBalance's balance in
place, year by year, exactly like 004's compare.py already has to guard
against across candidates -- here every *path* needs that same fresh,
independently-copied list, not just every candidate. Under serial dispatch
that's a plain per-call copy (_run_one_path()); under parallel dispatch the
base list is pickled once into a worker's shared state via
_init_worker()/initargs (the same "sent once per worker, not once per
task" mechanism household/accounts/strategy already use), and
_run_one_path_shared() takes its own fresh copy from that shared base
before every single path it's asked to run -- so mutations from one path
never leak into the next path the same worker process happens to run next.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

from retirement_planner.comparison import PlanProjection, StrategyConfiguration, run_plan_projection
from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
from retirement_planner.scenario import Household
from retirement_planner.tax import FigureUsage

from .models import PercentileBand, ReturnPath, SimulationRun, SurvivalCurve


def _fresh_inherited_accounts(inherited_accounts: list[InheritedAccountBalance]) -> list[InheritedAccountBalance]:
    """Mirrors comparison/compare.py's own helper of the same name exactly
    (research.md §10 addendum): a fresh, independently-copied list (and
    instances) must be built per run_plan_projection() call, since that
    function mutates each InheritedAccountBalance's balance in place."""
    return [replace(account) for account in inherited_accounts]


def _household_for_path(household: Household, death_year_draw: dict[str, int | None] | None) -> Household:
    """023-probabilistic-death-draws (rp-vgv), research.md §6: when
    death_year_draw is None (this capability unused, or this specific
    path has no draw), returns household unchanged -- the same object,
    no copy, so nothing downstream can differ from before this feature
    (FR-007). Otherwise returns a new Household whose members' own
    predicted_death_age is REPLACED (never merged with) that path's own
    drawn value for each member -- household.members[*].predicted_death_age
    itself is never mutated, exactly like household.filing_status is
    never mutated by 018's own per-year survivor-scenario switch.
    run_plan_projection() (018) needs no change at all: its existing
    _household_death_tax_year() helper already derives every downstream
    effect (filing status, survivor Social Security, spending reduction)
    purely from whatever Household it's given."""
    if death_year_draw is None:
        return household
    return replace(
        household,
        members=[
            replace(member, predicted_death_age=death_year_draw[member.person_name])
            for member in household.members
        ],
    )

# Below this path count, per-path work runs serially -- ProcessPoolExecutor
# start-up/IPC overhead outweighs the benefit for small runs, and (per the
# benchmark below) even for the full reference scale on typical hardware,
# since one plan-year's mechanics/tax chain costs well under a millisecond
# (research.md §7's original conservative estimate assumed tens of
# milliseconds). Set high enough that the documented reference scale
# (3,000-5,000 paths) runs serially by default; still exercised and
# correctness-tested above this threshold (tests/unit/simulation/test_monte_carlo.py,
# tests/integration/test_simulation_performance.py).
_PARALLEL_DISPATCH_THRESHOLD = 8_000

_DEFAULT_PERCENTILES: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75, 0.90)

# Per-worker-process state, set once via ProcessPoolExecutor's initializer
# rather than re-pickled on every one of thousands of tasks (research.md
# §7's parallel-dispatch mitigation only pays off once the *shared*
# arguments -- household, accounts, strategy -- are sent once per worker,
# not once per path).
_worker_shared_args: (
    tuple[
        Household, AccountBalances, dict[str, float], float, str, int, int, int, int, StrategyConfiguration,
        list[InheritedAccountBalance], bool,
    ]
    | None
) = None


def _init_worker(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    inherited_accounts: list[InheritedAccountBalance],
    net_earned_income_against_spending: bool,
) -> None:
    """ProcessPoolExecutor initializer: stores this call's arguments once
    per worker process into the module-level _worker_shared_args, so
    _run_one_path_shared() doesn't need them repickled per task
    (research.md §7). traditional_ownership_shares (011-per-owner-accounts)
    and inherited_accounts (012-inherited-ira-rmd rp-mt7) travel through
    this same shared-per-worker tuple, sent once per worker rather than
    once per path, exactly like household/accounts/strategy already are --
    inherited_accounts is this worker's own unmutated *base* list;
    _run_one_path_shared() takes a fresh copy of it before every path.
    net_earned_income_against_spending (rp-595) travels the same way."""
    global _worker_shared_args
    _worker_shared_args = (
        household, accounts, traditional_ownership_shares, annual_spending_need, state, reference_tax_year,
        start_plan_year, start_tax_year, plan_to_age, strategy, inherited_accounts,
        net_earned_income_against_spending,
    )


def _run_one_path_shared(task: tuple[ReturnPath, dict[str, int | None] | None]) -> PlanProjection:
    """Module-level (picklable) worker used under parallel dispatch: reads
    the shared, per-worker-process arguments _init_worker() set once, and
    runs run_plan_projection() for just this one path (research.md §7) --
    with its own fresh copy of inherited_accounts (module docstring),
    since this same worker process runs many paths in sequence and
    run_plan_projection() mutates each InheritedAccountBalance in place.

    task pairs this path's own ReturnPath with its own death-year draw
    (023-probabilistic-death-draws, rp-vgv, research.md §7) -- None when
    this capability is unused, in which case _household_for_path() is a
    complete no-op (FR-007)."""
    assert _worker_shared_args is not None
    return_path, death_year_draw = task
    (household, accounts, traditional_ownership_shares, annual_spending_need, state, reference_tax_year,
     start_plan_year, start_tax_year, plan_to_age, strategy, inherited_accounts,
     net_earned_income_against_spending) = _worker_shared_args
    return run_plan_projection(
        household=_household_for_path(household, death_year_draw),
        accounts=accounts,
        traditional_ownership_shares=traditional_ownership_shares,
        annual_spending_need=annual_spending_need,
        state=state,
        reference_tax_year=reference_tax_year,
        start_plan_year=start_plan_year,
        start_tax_year=start_tax_year,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_assumption=return_path,
        inherited_accounts=_fresh_inherited_accounts(inherited_accounts),
        net_earned_income_against_spending=net_earned_income_against_spending,
    )


def _run_one_path(
    args: tuple[
        Household, AccountBalances, dict[str, float], float, str, int, int, int, int, StrategyConfiguration,
        ReturnPath, list[InheritedAccountBalance], dict[str, int | None] | None, bool,
    ],
) -> PlanProjection:
    """Module-level (picklable) worker used under serial dispatch: unpacks
    one path's call arguments and runs run_plan_projection() for it, with
    its own fresh copy of inherited_accounts (module docstring).

    The trailing death_year_draw element (023-probabilistic-death-draws,
    rp-vgv, research.md §7) is None when this capability is unused, in
    which case _household_for_path() is a complete no-op (FR-007). The
    final net_earned_income_against_spending element (rp-595) travels the
    same way -- one extra positional element per path, not worth its own
    shared-per-worker tuple the way _run_one_path_shared() gets it."""
    (household, accounts, traditional_ownership_shares, annual_spending_need, state, reference_tax_year,
     start_plan_year, start_tax_year, plan_to_age, strategy, return_path, inherited_accounts,
     death_year_draw, net_earned_income_against_spending) = args
    return run_plan_projection(
        household=_household_for_path(household, death_year_draw),
        accounts=accounts,
        traditional_ownership_shares=traditional_ownership_shares,
        annual_spending_need=annual_spending_need,
        state=state,
        reference_tax_year=reference_tax_year,
        start_plan_year=start_plan_year,
        start_tax_year=start_tax_year,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_assumption=return_path,
        inherited_accounts=_fresh_inherited_accounts(inherited_accounts),
        net_earned_income_against_spending=net_earned_income_against_spending,
    )


def _dedupe_figures(figures: list[FigureUsage]) -> list[FigureUsage]:
    """Deduplicates by (name, last_verified), preserving first-seen order
    (FR-019, plan.md's figures_used union-not-derivation contract)."""
    seen: set[tuple[str, object]] = set()
    result: list[FigureUsage] = []
    for figure in figures:
        key = (figure.name, figure.last_verified)
        if key not in seen:
            seen.add(key)
            result.append(figure)
    return result


def _linear_percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation percentile (the standard "linear" method),
    implemented over the stdlib rather than a numeric array library
    (research.md §6)."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = p * (len(sorted_values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _percentile_bands(
    path_results: list[PlanProjection], percentiles: tuple[float, ...] = _DEFAULT_PERCENTILES
) -> list[PercentileBand]:
    """Derives PercentileBands entirely from path_results (data-model.md §
    Relationships) -- never computed independently of them."""
    if not path_results:
        return []
    horizon = len(path_results[0].years)
    bands: list[PercentileBand] = []
    for year_index in range(horizon):
        plan_year = path_results[0].years[year_index].plan_year
        ending_balances = sorted(
            projection.years[year_index].ending_balances.traditional
            + projection.years[year_index].ending_balances.roth
            + projection.years[year_index].ending_balances.taxable
            for projection in path_results
        )
        band_percentiles = {p: _linear_percentile(ending_balances, p) for p in percentiles}
        bands.append(PercentileBand(plan_year=plan_year, percentiles=band_percentiles))
    return bands


def run_simulation(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_paths: list[ReturnPath],
    candidate_label: str,
    survival_curves: dict[str, SurvivalCurve] | None = None,
    death_year_draws: list[dict[str, int | None]] | None = None,
    inherited_accounts: list[InheritedAccountBalance] = [],  # noqa: B006 -- see _fresh_inherited_accounts()
    net_earned_income_against_spending: bool = False,
) -> SimulationRun:
    """Calls run_plan_projection() once per entry in return_paths, each
    with that path substituted as the strategy's return_assumption
    (research.md §1), holding every other input fixed (FR-002). Aggregates
    into success_rate, percentile_bands, and (if survival_curves is given)
    survival_adjusted_success_rate (FR-003, FR-004, FR-017). Raises
    ValueError if return_paths is empty (FR-006). Raises KeyError if
    survival_curves is given but omits a household member's person_name
    (FR-018), or if traditional_ownership_shares (011-per-owner-accounts)
    omits one (comparison-api.md's precedent, applied here too) -- both
    validated eagerly, before any path is scored. See
    contracts/simulation-api.md.

    inherited_accounts (012-inherited-ira-rmd rp-mt7, module docstring):
    this call's own unmutated base list -- every individual path gets its
    own fresh, independently-copied list (_run_one_path()/
    _run_one_path_shared()), so this parameter itself is never mutated and
    may safely be reused across multiple run_simulation() calls (e.g. one
    per candidate in simulation/compare.py). Defaults to [], reproducing
    every existing caller's exact prior behavior.

    death_year_draws (023-probabilistic-death-draws, rp-vgv): optional,
    caller-pre-generated (simulation.mortality.generate_death_age_draws())
    per-path death-age draws -- None (the default) reproduces every
    existing caller's exact current behavior byte-for-byte (FR-007). When
    given, path i's own run_plan_projection() call runs against a
    Household whose members' predicted_death_age is REPLACED by
    death_year_draws[i]'s own values (_household_for_path()), reusing
    018's existing survivor-scenario mechanics unchanged -- no change to
    comparison/projection.py. Requires survival_curves also be given
    (ValueError otherwise) so this feature's own FigureUsage citation
    reuses the existing survival_curves-driven citation-attachment code
    below, rather than needing a second one (research.md §3). Raises
    ValueError if len(death_year_draws) != len(return_paths). Validated
    eagerly, before any path is scored, alongside every other check above.
    survival_adjusted_success_rate (if survival_curves is given) is
    computed exactly as it is today, unconditional on death_year_draws --
    the two capabilities coexist without changing each other's own
    computation (FR-008).

    net_earned_income_against_spending (rp-595): forwarded unchanged to
    every path's own run_plan_projection() call, both dispatch modes.
    Defaults to False, reproducing every existing caller's exact prior
    behavior unchanged.
    """
    if len(return_paths) == 0:
        raise ValueError("return_paths must contain at least one path")

    if survival_curves is not None:
        for member in household.members:
            if member.person_name not in survival_curves:
                raise KeyError(member.person_name)

    if death_year_draws is not None:
        if survival_curves is None:
            raise ValueError("death_year_draws requires survival_curves to also be given")
        if len(death_year_draws) != len(return_paths):
            raise ValueError(
                f"death_year_draws has {len(death_year_draws)} entries, expected {len(return_paths)} "
                "(one per entry in return_paths)"
            )

    for member in household.members:
        traditional_ownership_shares[member.person_name]  # noqa: B018 -- eager KeyError check

    # 023-probabilistic-death-draws: a same-length list of Nones when this
    # capability is unused, so both dispatch modes below run through one
    # code path uniformly regardless of whether it's in use -- see
    # _household_for_path()'s own docstring for why None is a true no-op.
    death_year_draws_by_path: list[dict[str, int | None] | None] = (
        list(death_year_draws) if death_year_draws is not None else [None] * len(return_paths)
    )

    if len(return_paths) >= _PARALLEL_DISPATCH_THRESHOLD:
        worker_count = os.cpu_count() or 4
        # A handful of chunks per worker balances load evenly across
        # workers without re-incurring per-task IPC overhead for every
        # single path (research.md §7) -- shared arguments are sent once
        # per worker via initargs, not once per path.
        chunk_size = max(1, len(return_paths) // (worker_count * 4))
        with ProcessPoolExecutor(
            initializer=_init_worker,
            initargs=(household, accounts, traditional_ownership_shares, annual_spending_need, state,
                      reference_tax_year, start_plan_year, start_tax_year, plan_to_age, strategy,
                      inherited_accounts, net_earned_income_against_spending),
        ) as executor:
            tasks = list(zip(return_paths, death_year_draws_by_path))
            path_results = list(executor.map(_run_one_path_shared, tasks, chunksize=chunk_size))
    else:
        call_args = [
            (household, accounts, traditional_ownership_shares, annual_spending_need, state, reference_tax_year,
             start_plan_year, start_tax_year, plan_to_age, strategy, path, inherited_accounts, draw,
             net_earned_income_against_spending)
            for path, draw in zip(return_paths, death_year_draws_by_path)
        ]
        path_results = [_run_one_path(args) for args in call_args]

    success_count = sum(1 for projection in path_results if projection.outcome.first_shortfall_plan_year is None)
    success_rate = success_count / len(path_results)

    percentile_bands = _percentile_bands(path_results)

    figures: list[FigureUsage] = []
    for projection, path in zip(path_results, return_paths):
        for year in projection.years:
            figures.extend(year.figures_used)
        figures.extend(path.figures_used)

    survival_adjusted_success_rate: float | None = None
    if survival_curves is not None:
        for member in household.members:
            figures.append(survival_curves[member.person_name].usage())

        survival_success_count = 0
        for projection in path_results:
            first_shortfall = projection.outcome.first_shortfall_plan_year
            if first_shortfall is None:
                survival_success_count += 1
                continue
            shortfall_year = next(year for year in projection.years if year.plan_year == first_shortfall)
            anyone_presumed_alive = any(
                survival_curves[member.person_name].survival_probability(
                    member.current_age + (shortfall_year.tax_year - reference_tax_year)
                )
                >= 0.5
                for member in household.members
            )
            if not anyone_presumed_alive:
                survival_success_count += 1
        survival_adjusted_success_rate = survival_success_count / len(path_results)

    return SimulationRun(
        candidate_label=candidate_label,
        strategy=strategy,
        state=state,
        path_results=path_results,
        success_rate=success_rate,
        percentile_bands=percentile_bands,
        survival_adjusted_success_rate=survival_adjusted_success_rate,
        figures_used=_dedupe_figures(figures),
    )
