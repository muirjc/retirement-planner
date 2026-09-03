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
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from retirement_planner.comparison import deemed_rmd_owner
from retirement_planner.reporting import compute_account_shares, summarize_run
from retirement_planner.scenario import ScenarioParseError
from retirement_planner.simulation import SimulationRun, generate_return_paths, run_simulation
from retirement_planner.tax import UnsupportedTaxYearError

from ..account_detail import PathIndexOutOfRangeError, build_account_detail_for_run, path_index_out_of_range_error
from ..cost_estimation import CostBudgetExceededError
from ..dependencies import get_scenarios_dir
from ..resolution import (
    BlockingValidationFlagsError,
    ResolvedRunContext,
    SurvivalCurveAgeOutOfRangeError,
    UnknownReferenceValueError,
    build_survival_curves,
    check_run_cost,
    resolve_run_context,
    survival_curve_age_out_of_range_error,
    unsupported_tax_year_error,
    validate_survival_curve_coverage,
)
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


def resolve_and_run_simulation(
    body: SimulationRequest, scenarios_dir: Path | None
) -> tuple[ResolvedRunContext, SimulationRun]:
    """Resolves body into a ResolvedRunContext (translating every
    resolution error into its documented HTTPException) and runs 005's
    generate_return_paths()+run_simulation(), returning both the context
    (the caller needs household/reference_tax_year for summarize_run()/
    run_to_csv_text()) and the raw SimulationRun -- neither summarized nor
    serialized yet."""
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

    # generate_return_paths() needs a single horizon_years count -- the
    # deemed owner's (the older member's) age is what run_plan_projection()
    # itself uses to decide when to stop, so mirror that here.
    owner = deemed_rmd_owner(context.household)
    horizon_years = context.plan_to_age - owner.current_age + 1

    return_paths = generate_return_paths(
        market_assumptions=context.scenario.market_assumptions,
        path_count=context.n_paths,
        horizon_years=horizon_years,
        start_plan_year=body.start_plan_year,
        seed=context.seed,
    )

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
        )
    except UnsupportedTaxYearError as exc:
        raise unsupported_tax_year_error(exc)
    return context, run


@router.post("/simulations")
def run_simulation_route(
    body: SimulationRequest, scenarios_dir: Path | None = Depends(get_scenarios_dir)
) -> dict:
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

    return {"run": to_jsonable(run), "summary": to_jsonable(summary), "account_detail": to_jsonable(account_detail)}
