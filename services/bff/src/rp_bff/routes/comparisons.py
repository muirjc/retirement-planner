"""POST /comparisons/deterministic and POST /comparisons/simulated
(FR-012-FR-015): dispatch by axis to 004's or 005's own compare_*()
functions, reusing the shared resolution helper for everything held fixed,
then 006's summarize_deterministic_comparison()/summarize_simulation_comparison().
See specs/007-bff-api-service/contracts/bff-api.md § Comparisons and
research.md §7 for why these are two endpoints, not one.

resolve_and_compare_deterministic()/resolve_and_compare_simulated() are the
reusable pieces routes/reports.py's comparison-export endpoint also calls
-- they return the raw ComparisonResult/SimulationComparisonResult, not
yet summarized or serialized, mirroring routes/simulations.py's
resolve_and_run_simulation() split.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from retirement_planner.comparison import ComparisonResult, deemed_rmd_owner
from retirement_planner.comparison import (
    compare_claiming_age_grid as compare_claiming_age_grid_deterministic,
    compare_roth_conversion_strategies as compare_roth_conversion_strategies_deterministic,
    compare_withdrawal_sequencing_strategies as compare_withdrawal_sequencing_strategies_deterministic,
    derive_deterministic_return,
)
from retirement_planner.mechanics import CONVERSION_STRATEGIES, WITHDRAWAL_STRATEGIES
from retirement_planner.reporting import compute_account_shares, summarize_deterministic_comparison, summarize_simulation_comparison
from retirement_planner.scenario import ScenarioParseError
from retirement_planner.simulation import SimulationComparisonResult, generate_return_paths
from retirement_planner.simulation import compare_claiming_age_grid as compare_claiming_age_grid_simulated
from retirement_planner.simulation import compare_roth_conversion_strategies as compare_roth_conversion_strategies_simulated
from retirement_planner.simulation import compare_states
from retirement_planner.simulation import (
    compare_withdrawal_sequencing_strategies as compare_withdrawal_sequencing_strategies_simulated,
)
from retirement_planner.tax import STATE_MODULES, UnsupportedTaxYearError

from ..account_detail import (
    PathIndexOutOfRangeError,
    build_account_detail_for_projection,
    build_account_detail_for_run,
    path_index_out_of_range_error,
)
from ..comparison_candidates import build_candidates_for_axis
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

DETERMINISTIC_AXES = {"roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"}
SIMULATED_AXES = {"state", "roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"}


class ComparisonRequest(BaseModel):
    """Shared request body for both comparison endpoints and
    POST /reports/comparisons.csv -- candidates' shape depends on axis,
    mirroring 004's/005's own compare_*() candidate parameters exactly
    (contracts/bff-api.md § Comparisons)."""

    scenario_name: str
    withdrawal_strategy: str | None = None
    state: str | None = None
    reference_tax_year: int
    start_plan_year: int
    start_tax_year: int
    plan_to_age: int | None = None
    n_paths: int | None = None
    seed: int | None = None
    axis: str
    candidates: list[Any]
    detail_path_index: int | None = None
    """015-per-account-projection-detail (contracts/bff-api.md): which
    path's account_detail to compute for the simulated route -- ignored
    by the deterministic route, where each candidate's own PlanProjection
    already *is* the one path. Defaults to 0 when omitted."""
    survival_adjusted: bool = False
    """rp-9vl: same opt-in flag as SimulationRequest's own -- honored only
    by resolve_and_compare_simulated() (005's compare_*() functions all
    accept survival_curves); silently ignored by
    resolve_and_compare_deterministic() (004 has no Monte Carlo
    distribution to score, mirroring detail_path_index's own "accepted but
    ignored by the deterministic route" precedent above)."""


def _resolve(body: ComparisonRequest, scenarios_dir: Path | None) -> ResolvedRunContext:
    """Shared scenario resolution for both comparison endpoints -- same
    error translation as routes/simulations.py's resolve_and_run_simulation()."""
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
            status_code=422, detail={"error": "blocking_validation_flags", "flags": to_jsonable(exc.flags)}
        )
    except UnknownReferenceValueError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "unknown_reference_value", "field": exc.field, "value": exc.value}
        )
    return context


def _reject_unknown(field: str, value: str) -> None:
    """The shared 422 shape for an unrecognized axis/state/strategy value
    (contracts/bff-api.md's unknown_reference_value error, FR-014)."""
    raise HTTPException(status_code=422, detail={"error": "unknown_reference_value", "field": field, "value": value})


def resolve_and_compare_deterministic(
    body: ComparisonRequest, scenarios_dir: Path | None
) -> tuple[ResolvedRunContext, ComparisonResult]:
    """Resolves body and dispatches to 004's compare_*() by axis (never
    "state" -- 004 has no state-comparison function, research.md §7),
    returning the raw ComparisonResult (not yet summarized/serialized) so
    both the JSON route and the CSV export route can reuse this exact
    computation (FR-012-FR-015)."""
    if body.axis not in DETERMINISTIC_AXES:
        _reject_unknown("axis", body.axis)

    context = _resolve(body, scenarios_dir)
    # claiming_age_grid candidates pass through unchanged (comparison_candidates.py)
    # and are never handed to build_candidates_for_axis, which raises
    # ValueError for any axis other than roth_conversion_strategy/
    # withdrawal_sequencing -- calling it unconditionally here 500'd every
    # claiming_age_grid comparison.
    candidates = (
        build_candidates_for_axis(body.axis, body.candidates, base_label=body.scenario_name)
        if body.axis != "claiming_age_grid"
        else None
    )
    return_assumption = derive_deterministic_return(context.scenario.market_assumptions)

    common = dict(
        household=context.household,
        accounts=context.accounts,
        traditional_ownership_shares=context.traditional_ownership_shares,
        annual_spending_need=context.scenario.spending.annual_need_real,
        state=context.state,
        reference_tax_year=body.reference_tax_year,
        start_plan_year=body.start_plan_year,
        start_tax_year=body.start_tax_year,
        plan_to_age=context.plan_to_age,
        return_assumption=return_assumption,
        # 010-advanced-tax-benefits: safe to force into every branch below --
        # unlike resolve_and_compare_simulated()'s own `common`, every
        # deterministic compare_*() function now accepts this parameter
        # (contracts/comparison-api.md), including compare_claiming_age_grid_deterministic.
        hsa_contribution=context.strategy.hsa_contribution,
        # 012-inherited-ira-rmd: likewise safe to force into every branch
        # below -- every deterministic compare_*() function now accepts
        # this parameter, each building its own fresh per-candidate copy
        # internally (comparison-api.md).
        inherited_accounts=context.inherited_accounts,
    )

    try:
        if body.axis == "roth_conversion_strategy":
            # rp-cgj: candidates is only None when body.axis ==
            # "claiming_age_grid" (the ternary above) -- this branch is the
            # opposite, so it's always a real list here.
            assert candidates is not None
            for candidate in candidates:
                if candidate.conversion_strategy is not None and candidate.conversion_strategy not in CONVERSION_STRATEGIES:
                    _reject_unknown("conversion_strategy", candidate.conversion_strategy)
            result = compare_roth_conversion_strategies_deterministic(
                **common, withdrawal_strategy=context.strategy.withdrawal_strategy,
                claiming_ages=context.strategy.claiming_ages, candidates=candidates,
            )
        elif body.axis == "withdrawal_sequencing":
            assert candidates is not None  # rp-cgj: see the roth_conversion_strategy branch's own comment above
            for candidate in candidates:
                if candidate.withdrawal_strategy not in WITHDRAWAL_STRATEGIES:
                    _reject_unknown("withdrawal_strategy", candidate.withdrawal_strategy)
            result = compare_withdrawal_sequencing_strategies_deterministic(
                **common, conversion_strategy=context.strategy.conversion_strategy,
                conversion_bracket_ceiling_or_amount=context.strategy.conversion_bracket_ceiling_or_amount,
                conversion_window=context.strategy.conversion_window,
                claiming_ages=context.strategy.claiming_ages, candidates=candidates,
            )
        else:  # claiming_age_grid
            try:
                result = compare_claiming_age_grid_deterministic(
                    **common, withdrawal_strategy=context.strategy.withdrawal_strategy,
                    conversion_strategy=context.strategy.conversion_strategy,
                    conversion_bracket_ceiling_or_amount=context.strategy.conversion_bracket_ceiling_or_amount,
                    conversion_window=context.strategy.conversion_window,
                    claiming_age_grid=body.candidates,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail={"error": "unknown_reference_value", "field": "claiming_age_grid", "value": str(exc)})
    except UnsupportedTaxYearError as exc:
        raise unsupported_tax_year_error(exc)

    return context, result


def resolve_and_compare_simulated(
    body: ComparisonRequest, scenarios_dir: Path | None
) -> tuple[ResolvedRunContext, SimulationComparisonResult]:
    """Resolves body and dispatches to 005's compare_*() by axis
    (including "state"), returning the raw SimulationComparisonResult (not
    yet summarized/serialized) so both the JSON route and the CSV export
    route can reuse this exact computation (FR-012-FR-015, FR-018)."""
    if body.axis not in SIMULATED_AXES:
        _reject_unknown("axis", body.axis)

    context = _resolve(body, scenarios_dir)

    if body.axis == "state":
        for state in body.candidates:
            if state not in STATE_MODULES:
                _reject_unknown("state", state)

    candidate_count = len(body.candidates) or 1
    try:
        check_run_cost(context, candidate_count=candidate_count)
    except CostBudgetExceededError as exc:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "estimated_cost_exceeds_budget",
                "estimated_seconds": exc.estimated_seconds,
                "budget_seconds": exc.budget_seconds,
            },
        )

    owner = deemed_rmd_owner(context.household)
    horizon_years = context.plan_to_age - owner.current_age + 1
    return_paths = generate_return_paths(
        market_assumptions=context.scenario.market_assumptions, path_count=context.n_paths,
        horizon_years=horizon_years, start_plan_year=body.start_plan_year, seed=context.seed,
    )

    # rp-9vl: same opt-in pre-flight check as resolve_and_run_simulation()'s
    # own -- see that function's comment for why this happens before any
    # compare_*() call rather than letting one discover the gap mid-run.
    survival_curves = None
    if body.survival_adjusted:
        survival_curves = build_survival_curves(context.household)
        try:
            validate_survival_curve_coverage(context.household, survival_curves, context.plan_to_age, owner.current_age)
        except SurvivalCurveAgeOutOfRangeError as exc:
            raise survival_curve_age_out_of_range_error(exc)

    common = dict(
        household=context.household,
        accounts=context.accounts,
        traditional_ownership_shares=context.traditional_ownership_shares,
        annual_spending_need=context.scenario.spending.annual_need_real,
        reference_tax_year=body.reference_tax_year,
        start_plan_year=body.start_plan_year,
        start_tax_year=body.start_tax_year,
        plan_to_age=context.plan_to_age,
        return_paths=return_paths,
        # 012-inherited-ira-rmd rp-mt7: now threaded through 005's
        # compare_*() the same way resolve_and_compare_deterministic()'s
        # own `common` already forces it into every deterministic branch.
        inherited_accounts=context.inherited_accounts,
        survival_curves=survival_curves,
    )

    try:
        if body.axis == "state":
            result = compare_states(**common, states=body.candidates, strategy=context.strategy)
        else:
            # claiming_age_grid candidates pass through unchanged (comparison_candidates.py)
            # and are never handed to build_candidates_for_axis, which raises
            # ValueError for any axis other than roth_conversion_strategy/
            # withdrawal_sequencing -- calling it unconditionally here 500'd
            # every claiming_age_grid comparison.
            candidates = (
                build_candidates_for_axis(body.axis, body.candidates, base_label=body.scenario_name)
                if body.axis != "claiming_age_grid"
                else None
            )
            if body.axis == "roth_conversion_strategy":
                # rp-cgj: candidates is only None when body.axis ==
                # "claiming_age_grid" (the ternary above) -- this branch is
                # the opposite, so it's always a real list here.
                assert candidates is not None
                for candidate in candidates:
                    if candidate.conversion_strategy is not None and candidate.conversion_strategy not in CONVERSION_STRATEGIES:
                        _reject_unknown("conversion_strategy", candidate.conversion_strategy)
                result = compare_roth_conversion_strategies_simulated(
                    **common, state=context.state, withdrawal_strategy=context.strategy.withdrawal_strategy,
                    claiming_ages=context.strategy.claiming_ages, candidates=candidates,
                    hsa_contribution=context.strategy.hsa_contribution,
                )
            elif body.axis == "withdrawal_sequencing":
                assert candidates is not None  # rp-cgj: see the roth_conversion_strategy branch's own comment above
                for candidate in candidates:
                    if candidate.withdrawal_strategy not in WITHDRAWAL_STRATEGIES:
                        _reject_unknown("withdrawal_strategy", candidate.withdrawal_strategy)
                result = compare_withdrawal_sequencing_strategies_simulated(
                    **common, state=context.state, conversion_strategy=context.strategy.conversion_strategy,
                    conversion_bracket_ceiling_or_amount=context.strategy.conversion_bracket_ceiling_or_amount,
                    conversion_window=context.strategy.conversion_window,
                    claiming_ages=context.strategy.claiming_ages, candidates=candidates,
                    hsa_contribution=context.strategy.hsa_contribution,
                )
            else:  # claiming_age_grid
                try:
                    result = compare_claiming_age_grid_simulated(
                        **common, state=context.state, withdrawal_strategy=context.strategy.withdrawal_strategy,
                        conversion_strategy=context.strategy.conversion_strategy,
                        conversion_bracket_ceiling_or_amount=context.strategy.conversion_bracket_ceiling_or_amount,
                        conversion_window=context.strategy.conversion_window,
                        claiming_age_grid=body.candidates,
                        hsa_contribution=context.strategy.hsa_contribution,
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail={"error": "unknown_reference_value", "field": "claiming_age_grid", "value": str(exc)})
    except UnsupportedTaxYearError as exc:
        raise unsupported_tax_year_error(exc)

    return context, result


@router.post("/comparisons/deterministic")
def compare_deterministic_route(
    body: ComparisonRequest, scenarios_dir: Path | None = Depends(get_scenarios_dir)
) -> dict:
    """POST /comparisons/deterministic (US4.2-US4.4)."""
    context, result = resolve_and_compare_deterministic(body, scenarios_dir)
    summaries = summarize_deterministic_comparison(result, household=context.household, reference_tax_year=body.reference_tax_year)

    # 015-per-account-projection-detail (US2): one candidate's own
    # PlanProjection already *is* the one path -- detail_path_index is
    # accepted but ignored here. compute_account_shares() runs once,
    # shared across every candidate (contracts/bff-api.md).
    shares = compute_account_shares(context.scenario.accounts)
    account_detail = [build_account_detail_for_projection(shares, projection) for projection in result.projections]

    return {"axis": body.axis, "summaries": to_jsonable(summaries), "account_detail": to_jsonable(account_detail)}


@router.post("/comparisons/simulated")
def compare_simulated_route(
    body: ComparisonRequest, scenarios_dir: Path | None = Depends(get_scenarios_dir)
) -> dict:
    """POST /comparisons/simulated (US4.1, US4.3-US4.4)."""
    context, result = resolve_and_compare_simulated(body, scenarios_dir)
    summaries = summarize_simulation_comparison(result, household=context.household, reference_tax_year=body.reference_tax_year)

    # 015-per-account-projection-detail (US2): one path per candidate's
    # own SimulationRun (default path 0) -- the first out-of-range
    # candidate's path_index is reported, mirroring /simulations' own
    # translation (contracts/bff-api.md).
    shares = compute_account_shares(context.scenario.accounts)
    try:
        account_detail = [build_account_detail_for_run(shares, run, body.detail_path_index) for run in result.runs]
    except PathIndexOutOfRangeError as exc:
        raise path_index_out_of_range_error(exc)

    return {"axis": body.axis, "summaries": to_jsonable(summaries), "account_detail": to_jsonable(account_detail)}
