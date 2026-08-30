"""Assembles the account_detail response field for POST /simulations and
POST /comparisons/* (015-per-account-projection-detail,
contracts/bff-api.md). Thin wiring over
retirement_planner.reporting.account_attribution, following resolution.py's/
serialization.py's one-module-per-concern layout -- performs no
computation of its own beyond what compute_account_shares()/
attribute_plan_projection() already do.

Callers compute AccountShares once per request (via
retirement_planner.reporting.compute_account_shares(context.scenario.accounts))
and pass the same list into every build_account_detail_for_*() call --
shared across every candidate in a comparison, never recomputed per
candidate, since it depends only on the request's own scenario, not on
any candidate's own result (contracts/bff-api.md).
"""

from __future__ import annotations

from fastapi import HTTPException

from retirement_planner.comparison import PlanProjection
from retirement_planner.reporting import AccountShare, PlanYearAccountDetail, attribute_plan_projection
from retirement_planner.simulation import SimulationRun


class PathIndexOutOfRangeError(Exception):
    """Raised when a requested detail_path_index has no corresponding
    path in a SimulationRun's path_results (contracts/bff-api.md)."""

    def __init__(self, requested: int, path_count: int) -> None:
        self.requested = requested
        self.path_count = path_count
        super().__init__(f"path_index {requested} out of range for {path_count} path(s)")


def path_index_out_of_range_error(exc: PathIndexOutOfRangeError) -> HTTPException:
    """Translates a raised PathIndexOutOfRangeError into a 422 response,
    mirroring resolution.py's own unsupported_tax_year_error() shape."""
    return HTTPException(
        status_code=422,
        detail={"error": "path_index_out_of_range", "requested": exc.requested, "path_count": exc.path_count},
    )


def build_account_detail_for_projection(
    shares: list[AccountShare], projection: PlanProjection
) -> list[PlanYearAccountDetail]:
    """For a deterministic candidate, a PlanProjection *is* the one path
    -- no path selection needed."""
    return attribute_plan_projection(projection, shares)


def build_account_detail_for_run(
    shares: list[AccountShare], run: SimulationRun, path_index: int | None
) -> list[PlanYearAccountDetail]:
    """path_index defaults to 0 (export.py's own "path 0 is
    representative" precedent) when omitted. Raises PathIndexOutOfRangeError
    -- never silently substituted or crashed on -- when out of
    [0, len(run.path_results))."""
    index = path_index if path_index is not None else 0
    if index < 0 or index >= len(run.path_results):
        raise PathIndexOutOfRangeError(requested=index, path_count=len(run.path_results))
    return attribute_plan_projection(run.path_results[index], shares)
