"""Return-path generation (FR-001, FR-012, FR-014): parametric
correlated-normal draws (US1), historical-bootstrap resampling (US3), and
sequence-of-returns stress overlay (US4). See
specs/005-simulation-engine/research.md §3-4, §6 and
contracts/simulation-api.md.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace

from retirement_planner.scenario import MarketAssumptions

from .historical_data import HISTORICAL_RETURNS
from .models import ReturnPath, StressScenario


def generate_return_paths(
    market_assumptions: MarketAssumptions,
    path_count: int,
    horizon_years: int,
    start_plan_year: int,
    seed: int,
) -> list[ReturnPath]:
    """Generates path_count independent ReturnPaths, each horizon_years
    long starting at start_plan_year, via the correlated-normal transform
    (research.md §3): a single random.Random(seed) instance is consumed in
    a fixed order -- path 0's years in order, then path 1's, etc., two
    .gauss() calls per plan year (z1 before z2) -- so the sequence is fully
    determined by seed alone (FR-001, FR-005). Raises ValueError if
    path_count <= 0 (FR-006). generation_mode="parametric";
    figures_used=[] for every path, since this is user-supplied market
    opinion, not a citable fact (research.md §3, mirrors 004's Decision 1).
    """
    if path_count <= 0:
        raise ValueError(f"path_count must be positive, got {path_count}")

    rng = random.Random(seed)
    sqrt_one_minus_corr_sq = math.sqrt(1.0 - market_assumptions.correlation**2)

    paths: list[ReturnPath] = []
    for _ in range(path_count):
        annual_returns: list[float] = []
        for _ in range(horizon_years):
            z1 = rng.gauss(0.0, 1.0)
            z2 = rng.gauss(0.0, 1.0)
            equity_return = market_assumptions.equity_return_mean_real + market_assumptions.equity_return_std_real * z1
            bond_return = market_assumptions.bond_return_mean_real + market_assumptions.bond_return_std_real * (
                market_assumptions.correlation * z1 + sqrt_one_minus_corr_sq * z2
            )
            blended_return = (
                market_assumptions.equity_allocation * equity_return
                + market_assumptions.bond_allocation * bond_return
            )
            annual_returns.append(blended_return)
        paths.append(
            ReturnPath(
                start_plan_year=start_plan_year,
                annual_returns=annual_returns,
                generation_mode="parametric",
                figures_used=[],
            )
        )
    return paths


def generate_historical_bootstrap_paths(
    market_assumptions: MarketAssumptions,
    path_count: int,
    horizon_years: int,
    start_plan_year: int,
    seed: int,
    block_length: int,
) -> list[ReturnPath]:
    """Generates path_count independent ReturnPaths via moving-block
    bootstrap resampling from HISTORICAL_RETURNS (research.md §4):
    repeatedly picks a random contiguous block_length-year window from the
    documented historical years, concatenates blocks until horizon_years is
    reached, truncates to exactly horizon_years. Each drawn year's
    (equity_return, bond_return) pair is blended using
    market_assumptions.equity_allocation/bond_allocation, the same
    allocation-weighting formula generate_return_paths() uses -- only those
    two fields are read from market_assumptions in this mode (FR-012).
    Raises ValueError if block_length exceeds the number of documented
    historical years, or if block_length <= 0 or path_count <= 0 (FR-013).
    """
    if path_count <= 0:
        raise ValueError(f"path_count must be positive, got {path_count}")
    if block_length <= 0:
        raise ValueError(f"block_length must be positive, got {block_length}")

    documented_years = sorted(HISTORICAL_RETURNS.schedule.keys())
    if block_length > len(documented_years):
        raise ValueError(
            f"block_length {block_length} exceeds the {len(documented_years)} documented historical years"
        )

    max_start_index = len(documented_years) - block_length
    rng = random.Random(seed)

    paths: list[ReturnPath] = []
    for _ in range(path_count):
        annual_returns: list[float] = []
        figures_used = []
        while len(annual_returns) < horizon_years:
            start_index = rng.randrange(0, max_start_index + 1)
            for offset in range(block_length):
                if len(annual_returns) >= horizon_years:
                    break
                year = documented_years[start_index + offset]
                equity_return, bond_return = HISTORICAL_RETURNS.schedule[year]
                blended_return = (
                    market_assumptions.equity_allocation * equity_return
                    + market_assumptions.bond_allocation * bond_return
                )
                annual_returns.append(blended_return)
                figures_used.append(HISTORICAL_RETURNS.usage_for_year(year))
        paths.append(
            ReturnPath(
                start_plan_year=start_plan_year,
                annual_returns=annual_returns,
                generation_mode="historical_bootstrap",
                figures_used=figures_used,
            )
        )
    return paths


def apply_stress_scenario(
    paths: list[ReturnPath],
    stress: StressScenario,
    horizon_last_plan_year: int,
) -> list[ReturnPath]:
    """Returns a new list[ReturnPath] (paths is not mutated) with every
    path's annual_returns overridden to stress.magnitude for plan years in
    [stress.start_plan_year, stress.start_plan_year + stress.duration_years),
    every other year unchanged, generation_mode and figures_used carried
    through unchanged (FR-014, FR-016). Raises ValueError if
    stress.start_plan_year + stress.duration_years - 1 > horizon_last_plan_year
    (FR-015).
    """
    window_last_plan_year = stress.start_plan_year + stress.duration_years - 1
    if window_last_plan_year > horizon_last_plan_year:
        raise ValueError(
            f"stress window ends at plan year {window_last_plan_year}, "
            f"beyond the horizon's last plan year {horizon_last_plan_year}"
        )

    stressed_paths: list[ReturnPath] = []
    for path in paths:
        new_annual_returns = list(path.annual_returns)
        for plan_year in range(stress.start_plan_year, stress.start_plan_year + stress.duration_years):
            index = plan_year - path.start_plan_year
            if 0 <= index < len(new_annual_returns):
                new_annual_returns[index] = stress.magnitude
        stressed_paths.append(replace(path, annual_returns=new_annual_returns))
    return stressed_paths
