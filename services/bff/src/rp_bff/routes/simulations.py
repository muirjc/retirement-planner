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
from retirement_planner.reporting import summarize_run
from retirement_planner.scenario import ScenarioParseError
from retirement_planner.simulation import SimulationRun, generate_return_paths, run_simulation
from retirement_planner.tax import UnsupportedTaxYearError

from ..cost_estimation import CostBudgetExceededError
from ..dependencies import get_scenarios_dir
from ..resolution import (
    BlockingValidationFlagsError,
    ResolvedRunContext,
    UnknownReferenceValueError,
    check_run_cost,
    resolve_run_context,
    unsupported_tax_year_error,
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
    return {"run": to_jsonable(run), "summary": to_jsonable(summary)}
