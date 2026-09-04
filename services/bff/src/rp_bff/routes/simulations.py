"""POST /simulations (FR-008): resolves the request via the shared
resolution helper, then calls 005's generate_return_paths()+
run_simulation() and 006's summarize_run() unchanged, returning both in
one response. See specs/007-bff-api-service/contracts/bff-api.md §
Simulations.

resolve_and_run_simulation() is the reusable piece routes/reports.py's
run-export endpoint also calls (research.md's "same request shape as the
trigger endpoint" design for exports) -- it returns the raw SimulationRun,
not yet summarized or serialized, so both consumers can apply their own
006 function (summarize_run() here, run_to_csv_text() in reports.py) to
the identical resolved computation.

Also POST /simulations/sustainable-spending-range (rp-9hl): a real,
simulation-backed search over run_simulation()'s own success_rate output
for what a scenario's household can actually afford to spend -- see
docs/BRD.md §6.10 and resolve_and_search_sustainable_spending()'s own
docstring below.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from retirement_planner.comparison import deemed_rmd_owner
from retirement_planner.reporting import build_narrative_for_run, compute_account_shares, summarize_run
from retirement_planner.scenario import ScenarioParseError
from retirement_planner.simulation import (
    GenerationMode,
    SimulationRun,
    StressScenario,
    SustainableSpendingRangeResult,
    find_sustainable_spending_range,
    run_simulation,
)
from retirement_planner.tax import UnsupportedTaxYearError

from ..account_detail import PathIndexOutOfRangeError, build_account_detail_for_run, path_index_out_of_range_error
from ..cost_estimation import CostBudgetExceededError, check_cost_within_budget
from ..dependencies import get_scenarios_dir
from ..resolution import (
    BlockingValidationFlagsError,
    ResolvedRunContext,
    SurvivalCurveAgeOutOfRangeError,
    UnknownReferenceValueError,
    build_survival_curves,
    check_run_cost,
    generate_configured_return_paths,
    invalid_simulation_options_error,
    resolve_run_context,
    survival_curve_age_out_of_range_error,
    unsupported_tax_year_error,
    validate_survival_curve_coverage,
)
from ..schemas import StressScenarioRequest
from ..serialization import to_jsonable

router = APIRouter()


class SimulationRequest(BaseModel):
    """POST /simulations and POST /reports/simulations.csv's shared
    request body -- contracts/bff-api.md § Simulations."""

    scenario_name: str
    withdrawal_strategy: str | None = None
    state: str | None = None
    reference_tax_year: int
    start_plan_year: int
    start_tax_year: int
    plan_to_age: int | None = None
    n_paths: int | None = None
    seed: int | None = None
    detail_path_index: int | None = None
    """015-per-account-projection-detail (contracts/bff-api.md): which
    path's account_detail to compute -- defaults to 0 (export.py's own
    "path 0 is representative" precedent) when omitted."""
    survival_adjusted: bool = False
    """rp-9vl: opt-in flag for SimulationRun.survival_adjusted_success_rate
    -- when True, every household member is given a per-member
    SurvivalCurve built from simulation.SURVIVAL_TABLE's illustrative
    "primary"/"spouse" curves (there is no per-scenario user-entered
    survival-curve data; a v1 needs none). False (the default) reproduces
    every existing request's exact current behavior byte-for-byte."""
    generation_mode: GenerationMode = "parametric"
    """rp-741 (026-advanced-simulation-options): "parametric" (default,
    every existing request's exact current behavior) or
    "historical_bootstrap" (opt-in moving-block resampling from
    HISTORICAL_RETURNS -- synthetic placeholder data, docs/BRD.md §6.9;
    surfaced via the existing unverified-figure pipeline, not silently
    presented as real historical returns)."""
    historical_block_length: int = 10
    """rp-741: consulted only when generation_mode ==
    "historical_bootstrap" (026 research.md Decision 4's default, matching
    005-simulation-engine's own quickstart.md worked example). Ignored,
    harmlessly present, in parametric mode."""
    stress_scenario: StressScenarioRequest | None = None
    """rp-2bn (026-advanced-simulation-options): None (default) means no
    sequence-of-returns stress overlay -- every existing request's exact
    current behavior. Applied on top of whichever generation_mode produced
    the underlying paths."""


def resolve_and_run_simulation(body: SimulationRequest, scenarios_dir: Path | None) -> tuple[ResolvedRunContext, SimulationRun]:
    """Resolves body into a ResolvedRunContext (translating every
    resolution error into its documented HTTPException) and runs
    resolution.generate_configured_return_paths() (026-advanced-simulation-
    options -- dispatches to 005's generate_return_paths() or
    generate_historical_bootstrap_paths() per body.generation_mode, then
    optionally applies apply_stress_scenario())+run_simulation(), returning
    both the context (the caller needs household/reference_tax_year for
    summarize_run()/run_to_csv_text()) and the raw SimulationRun -- neither
    summarized nor serialized yet."""
    try:
        context = resolve_run_context(
            body.scenario_name,
            withdrawal_strategy=body.withdrawal_strategy,
            state=body.state,
            plan_to_age=body.plan_to_age,
            n_paths=body.n_paths,
            seed=body.seed,
            reference_tax_year=body.reference_tax_year,
            scenarios_dir=scenarios_dir,
        )
    except ScenarioParseError:
        raise HTTPException(status_code=404, detail={"error": "no_such_scenario", "name": body.scenario_name})
    except BlockingValidationFlagsError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "blocking_validation_flags", "flags": to_jsonable(exc.flags)},
        )
    except UnknownReferenceValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "unknown_reference_value", "field": exc.field, "value": exc.value},
        )

    try:
        check_run_cost(context)
    except CostBudgetExceededError as exc:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "estimated_cost_exceeds_budget",
                "estimated_seconds": exc.estimated_seconds,
                "budget_seconds": exc.budget_seconds,
            },
        )

    # generate_configured_return_paths() needs a single horizon_years count
    # -- the deemed owner's (the older member's) age is what
    # run_plan_projection() itself uses to decide when to stop, so mirror
    # that here.
    owner = deemed_rmd_owner(context.household)
    horizon_years = context.plan_to_age - owner.current_age + 1

    stress_scenario = (
        StressScenario(
            magnitude=body.stress_scenario.magnitude,
            duration_years=body.stress_scenario.duration_years,
            start_plan_year=body.stress_scenario.start_plan_year,
        )
        if body.stress_scenario is not None
        else None
    )
    try:
        return_paths = generate_configured_return_paths(
            context,
            horizon_years=horizon_years,
            start_plan_year=body.start_plan_year,
            generation_mode=body.generation_mode,
            historical_block_length=body.historical_block_length,
            stress_scenario=stress_scenario,
        )
    except ValueError as exc:
        raise invalid_simulation_options_error(exc)

    # rp-9vl: opt-in, so every existing request (survival_adjusted omitted
    # or False) reaches run_simulation() with survival_curves=None,
    # reproducing its exact prior behavior byte-for-byte.
    survival_curves = None
    if body.survival_adjusted:
        survival_curves = build_survival_curves(context.household)
        try:
            validate_survival_curve_coverage(context.household, survival_curves, context.plan_to_age, owner.current_age)
        except SurvivalCurveAgeOutOfRangeError as exc:
            raise survival_curve_age_out_of_range_error(exc)

    try:
        run = run_simulation(
            household=context.household,
            accounts=context.accounts,
            traditional_ownership_shares=context.traditional_ownership_shares,
            annual_spending_need=context.scenario.spending.annual_need_real,
            state=context.state,
            reference_tax_year=body.reference_tax_year,
            start_plan_year=body.start_plan_year,
            start_tax_year=body.start_tax_year,
            plan_to_age=context.plan_to_age,
            strategy=context.strategy,
            return_paths=return_paths,
            candidate_label=body.scenario_name,
            inherited_accounts=context.inherited_accounts,
            survival_curves=survival_curves,
            net_earned_income_against_spending=context.net_earned_income_against_spending,
        )
    except UnsupportedTaxYearError as exc:
        raise unsupported_tax_year_error(exc)
    return context, run


@router.post("/simulations")
def run_simulation_route(body: SimulationRequest, scenarios_dir: Path | None = Depends(get_scenarios_dir)) -> dict:
    """POST /simulations -- run + summary in one response (FR-008, US3.1)."""
    context, run = resolve_and_run_simulation(body, scenarios_dir)
    summary = summarize_run(run, household=context.household, reference_tax_year=body.reference_tax_year)

    # 015-per-account-projection-detail (contracts/bff-api.md, US1):
    # computed for exactly one path, regardless of how many the
    # simulation ran -- never once per path.
    shares = compute_account_shares(context.scenario.accounts)
    try:
        account_detail = build_account_detail_for_run(shares, run, body.detail_path_index)
    except PathIndexOutOfRangeError as exc:
        raise path_index_out_of_range_error(exc)

    # 028-results-walkthrough (rp-bm8.1, contracts/reporting-narrative-api.md):
    # computed once, for build_narrative_for_run()'s own selected
    # representative path -- independent of body.detail_path_index above,
    # which governs account_detail's separately-selected path.
    narrative = build_narrative_for_run(run, household=context.household, reference_tax_year=body.reference_tax_year)

    return {
        "run": to_jsonable(run),
        "summary": to_jsonable(summary),
        "account_detail": to_jsonable(account_detail),
        "narrative": to_jsonable(narrative),
    }


# -- rp-9hl: sustainable-spending range search --------------------------------

_SEARCH_PATH_COUNT = 200
"""rp-9hl: a search runs 10s of simulations, not one -- deliberately far
below a typical full-precision n_paths (context.n_paths, whatever the
scenario/request itself configures) so the search's own pre-flight cost
estimate (below) stays well within budget across realistic horizons.
docs/BRD.md §6.10: the resulting range is reported as an explicit
estimate, never full precision, exactly because of this reduction."""

_MAX_BRACKET_EXPANSIONS = 6
_MAX_BISECTION_ITERATIONS = 10
_MAX_ITERATIONS_PER_SEARCH = 1 + _MAX_BRACKET_EXPANSIONS + _MAX_BISECTION_ITERATIONS
"""1 initial rate check + up to _MAX_BRACKET_EXPANSIONS doublings + up to
_MAX_BISECTION_ITERATIONS bisection steps -- see
spending_search.search_spending_for_target_success_rate()'s own docstring
for exactly how these bound the search. Smaller than that function's own
generic defaults (10/15) specifically so this endpoint's pre-flight cost
estimate below (two searches' worth) stays comfortably inside the
constitution's performance budget for the horizons this tool's own
worked examples span."""


class SustainableSpendingRangeRequest(BaseModel):
    """POST /simulations/sustainable-spending-range's request body --
    mirrors SimulationRequest's own scenario-resolution fields exactly
    (n_paths/seed omitted -- the search always uses its own fixed,
    reduced _SEARCH_PATH_COUNT/context.seed, never a caller-chosen
    n_paths meant for a full-precision single run; survival_adjusted/
    detail_path_index omitted -- out of scope for a search, which scores
    plain success_rate only, not survival-adjusted scoring or a specific
    path's own account detail)."""

    scenario_name: str
    withdrawal_strategy: str | None = None
    state: str | None = None
    reference_tax_year: int
    start_plan_year: int
    start_tax_year: int
    plan_to_age: int | None = None
    generation_mode: GenerationMode = "parametric"
    historical_block_length: int = 10
    stress_scenario: StressScenarioRequest | None = None
    conservative_target_success_rate: float = 0.95
    flexible_target_success_rate: float = 0.75


def resolve_and_search_sustainable_spending(
    body: SustainableSpendingRangeRequest, scenarios_dir: Path | None
) -> tuple[ResolvedRunContext, SustainableSpendingRangeResult]:
    """Mirrors resolve_and_run_simulation()'s own resolution flow, but
    calls find_sustainable_spending_range() instead of run_simulation()
    once -- see that function's own docstring and docs/BRD.md §6.10 for
    the search algorithm and its reduced-precision disclosure."""
    try:
        context = resolve_run_context(
            body.scenario_name,
            withdrawal_strategy=body.withdrawal_strategy,
            state=body.state,
            plan_to_age=body.plan_to_age,
            n_paths=None,
            seed=None,
            reference_tax_year=body.reference_tax_year,
            scenarios_dir=scenarios_dir,
        )
    except ScenarioParseError:
        raise HTTPException(status_code=404, detail={"error": "no_such_scenario", "name": body.scenario_name})
    except BlockingValidationFlagsError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "blocking_validation_flags", "flags": to_jsonable(exc.flags)},
        )
    except UnknownReferenceValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "unknown_reference_value", "field": exc.field, "value": exc.value},
        )

    owner = deemed_rmd_owner(context.household)
    horizon_years = context.plan_to_age - owner.current_age + 1

    # rp-9hl: two searches' worth of iterations, at the search's own
    # reduced path count -- never context.n_paths, which reflects a
    # full-precision single-run preference this endpoint doesn't use.
    try:
        check_cost_within_budget(
            path_count=_SEARCH_PATH_COUNT,
            candidate_count=2 * _MAX_ITERATIONS_PER_SEARCH,
            horizon_years=horizon_years,
        )
    except CostBudgetExceededError as exc:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "estimated_cost_exceeds_budget",
                "estimated_seconds": exc.estimated_seconds,
                "budget_seconds": exc.budget_seconds,
            },
        )

    stress_scenario = (
        StressScenario(
            magnitude=body.stress_scenario.magnitude,
            duration_years=body.stress_scenario.duration_years,
            start_plan_year=body.stress_scenario.start_plan_year,
        )
        if body.stress_scenario is not None
        else None
    )
    try:
        return_paths = generate_configured_return_paths(
            context,
            horizon_years=horizon_years,
            start_plan_year=body.start_plan_year,
            generation_mode=body.generation_mode,
            historical_block_length=body.historical_block_length,
            stress_scenario=stress_scenario,
            path_count=_SEARCH_PATH_COUNT,
        )
    except ValueError as exc:
        raise invalid_simulation_options_error(exc)

    try:
        result = find_sustainable_spending_range(
            household=context.household,
            accounts=context.accounts,
            traditional_ownership_shares=context.traditional_ownership_shares,
            state=context.state,
            reference_tax_year=body.reference_tax_year,
            start_plan_year=body.start_plan_year,
            start_tax_year=body.start_tax_year,
            plan_to_age=context.plan_to_age,
            strategy=context.strategy,
            return_paths=return_paths,
            anchor_spending=context.scenario.spending.annual_need_real,
            conservative_target_success_rate=body.conservative_target_success_rate,
            flexible_target_success_rate=body.flexible_target_success_rate,
            inherited_accounts=context.inherited_accounts,
            net_earned_income_against_spending=context.net_earned_income_against_spending,
            max_bracket_expansions=_MAX_BRACKET_EXPANSIONS,
            max_bisection_iterations=_MAX_BISECTION_ITERATIONS,
        )
    except UnsupportedTaxYearError as exc:
        raise unsupported_tax_year_error(exc)
    return context, result


@router.post("/simulations/sustainable-spending-range")
def search_sustainable_spending_range_route(
    body: SustainableSpendingRangeRequest, scenarios_dir: Path | None = Depends(get_scenarios_dir)
) -> dict:
    """POST /simulations/sustainable-spending-range (rp-9hl) -- a real,
    simulation-backed estimate of what this scenario's household can
    afford to spend, at a reduced path count for speed (docs/BRD.md
    §6.10). Response: {"conservative": {...}, "flexible": {...},
    "path_count_used": int} -- each of conservative/flexible is a
    SpendingSearchResult (spending, achieved_success_rate,
    target_success_rate, iterations_used, bracket_exhausted)."""
    _context, result = resolve_and_search_sustainable_spending(body, scenarios_dir)
    return to_jsonable(result)
