"""Reference-data routes (FR-006-FR-007): live lists of supported states,
withdrawal strategies, conversion strategies, and comparison axes -- read
directly from 002/003/005's own registries on every request, never a
separately maintained or cached copy (Acceptance Scenario US2.2,
Principle IV). See specs/007-bff-api-service/contracts/bff-api.md §
Reference data.
"""

from __future__ import annotations

import typing

from fastapi import APIRouter

from retirement_planner.mechanics import CONVERSION_STRATEGIES, WITHDRAWAL_STRATEGIES
from retirement_planner.simulation.models import ComparisonAxis
from retirement_planner.tax import STATE_MODULES

router = APIRouter()


@router.get("/reference/states")
def list_states_route() -> dict:
    """GET /reference/states -- live from 002's STATE_MODULES (FR-006, US2.1-US2.2)."""
    return {"states": sorted(STATE_MODULES.keys())}


@router.get("/reference/withdrawal-strategies")
def list_withdrawal_strategies_route() -> dict:
    """GET /reference/withdrawal-strategies -- live from 003's WITHDRAWAL_STRATEGIES (FR-007, US2.3)."""
    return {"withdrawal_strategies": sorted(WITHDRAWAL_STRATEGIES.keys())}


@router.get("/reference/conversion-strategies")
def list_conversion_strategies_route() -> dict:
    """GET /reference/conversion-strategies -- live from 003's CONVERSION_STRATEGIES (FR-007, US2.3)."""
    return {"conversion_strategies": sorted(CONVERSION_STRATEGIES.keys())}


@router.get("/reference/comparison-axes")
def list_comparison_axes_route() -> dict:
    """GET /reference/comparison-axes -- live from 005's ComparisonAxis
    type (FR-007, US2.3). Note: this is 005's full axis set, including
    "state" -- /comparisons/deterministic accepts only the subset 004's
    ComparisonDimension defines (research.md §7)."""
    return {"axes": sorted(typing.get_args(ComparisonAxis))}
