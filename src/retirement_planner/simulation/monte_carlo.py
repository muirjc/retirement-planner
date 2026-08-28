"""Multi-path Monte Carlo simulation (FR-002-FR-004, FR-006, FR-017-FR-019):
runs run_plan_projection() once per ReturnPath, aggregating into a success
rate, percentile ending-balance bands, and (optionally) a survival-adjusted
success rate. Path-level work is dispatched across worker processes once
path_count exceeds a threshold (research.md §7). See
specs/005-simulation-engine/contracts/simulation-api.md.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

from retirement_planner.comparison import PlanProjection, StrategyConfiguration, run_plan_projection
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household
from retirement_planner.tax import FigureUsage

from .models import PercentileBand, ReturnPath, SimulationRun, SurvivalCurve

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
_worker_shared_args: tuple[Household, AccountBalances, float, str, int, int, int, int, StrategyConfiguration] | None = None


def _init_worker(
    household: Household,
    accounts: AccountBalances,
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
) -> None:
    """ProcessPoolExecutor initializer: stores this call's arguments once
    per worker process into the module-level _worker_shared_args, so
    _run_one_path_shared() doesn't need them repickled per task
    (research.md §7)."""
    global _worker_shared_args
    _worker_shared_args = (
        household, accounts, annual_spending_need, state, reference_tax_year, start_plan_year, start_tax_year,
        plan_to_age, strategy,
    )


def _run_one_path_shared(return_path: ReturnPath) -> PlanProjection:
    """Module-level (picklable) worker used under parallel dispatch: reads
    the shared, per-worker-process arguments _init_worker() set once, and
    runs run_plan_projection() for just this one path (research.md §7)."""
    assert _worker_shared_args is not None
    (household, accounts, annual_spending_need, state, reference_tax_year, start_plan_year, start_tax_year,
     plan_to_age, strategy) = _worker_shared_args
    return run_plan_projection(
        household=household,
        accounts=accounts,
        annual_spending_need=annual_spending_need,
        state=state,
        reference_tax_year=reference_tax_year,
        start_plan_year=start_plan_year,
        start_tax_year=start_tax_year,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_assumption=return_path,
    )


def _run_one_path(
    args: tuple[Household, AccountBalances, float, str, int, int, int, int, StrategyConfiguration, ReturnPath],
) -> PlanProjection:
    """Module-level (picklable) worker used under serial dispatch: unpacks
    one path's call arguments and runs run_plan_projection() for it."""
    (household, accounts, annual_spending_need, state, reference_tax_year, start_plan_year, start_tax_year,
     plan_to_age, strategy, return_path) = args
    return run_plan_projection(
        household=household,
        accounts=accounts,
        annual_spending_need=annual_spending_need,
        state=state,
        reference_tax_year=reference_tax_year,
        start_plan_year=start_plan_year,
        start_tax_year=start_tax_year,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_assumption=return_path,
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
) -> SimulationRun:
    """Calls run_plan_projection() once per entry in return_paths, each
    with that path substituted as the strategy's return_assumption
    (research.md §1), holding every other input fixed (FR-002). Aggregates
    into success_rate, percentile_bands, and (if survival_curves is given)
    survival_adjusted_success_rate (FR-003, FR-004, FR-017). Raises
    ValueError if return_paths is empty (FR-006). Raises KeyError if
    survival_curves is given but omits a household member's person_name
    (FR-018) -- validated eagerly, before any path is scored. See
    contracts/simulation-api.md."""
    if len(return_paths) == 0:
        raise ValueError("return_paths must contain at least one path")

    if survival_curves is not None:
        for member in household.members:
            if member.person_name not in survival_curves:
                raise KeyError(member.person_name)

    if len(return_paths) >= _PARALLEL_DISPATCH_THRESHOLD:
        worker_count = os.cpu_count() or 4
        # A handful of chunks per worker balances load evenly across
        # workers without re-incurring per-task IPC overhead for every
        # single path (research.md §7) -- shared arguments are sent once
        # per worker via initargs, not once per path.
        chunk_size = max(1, len(return_paths) // (worker_count * 4))
        with ProcessPoolExecutor(
            initializer=_init_worker,
            initargs=(household, accounts, annual_spending_need, state, reference_tax_year, start_plan_year,
                      start_tax_year, plan_to_age, strategy),
        ) as executor:
            path_results = list(executor.map(_run_one_path_shared, return_paths, chunksize=chunk_size))
    else:
        call_args = [
            (household, accounts, annual_spending_need, state, reference_tax_year, start_plan_year, start_tax_year,
             plan_to_age, strategy, path)
            for path in return_paths
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
