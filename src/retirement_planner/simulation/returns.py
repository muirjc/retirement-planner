"""Return-path generation (rp-aev): parametric correlated-normal draws,
historical-bootstrap resampling, and sequence-of-returns stress overlay,
across 8 asset classes. See scenario/correlation.py's cholesky_lower() for
the shared "is this a valid correlation matrix" primitive this module's
real draw relies on (also reused by scenario/validation.py's pre-flight
check, so the two can never disagree about what counts as valid).
"""

from __future__ import annotations

import random
from dataclasses import replace

from retirement_planner.scenario import ASSET_CLASSES, AssetClass, MarketAssumptions, cholesky_lower

from .historical_data import HISTORICAL_RETURNS
from .models import AssetClassReturnPath, StressScenario

_ASSET_CLASS_COUNT = len(ASSET_CLASSES)


def generate_return_paths(
    market_assumptions: MarketAssumptions,
    path_count: int,
    horizon_years: int,
    start_plan_year: int,
    seed: int,
) -> list[AssetClassReturnPath]:
    """Generates path_count independent AssetClassReturnPaths, each
    horizon_years long starting at start_plan_year. A single
    random.Random(seed) instance is consumed in a fixed order -- path 0's
    years in order, then path 1's, etc., 8 independent .gauss(0,1) calls
    per plan year in ASSET_CLASSES order -- so the sequence is fully
    determined by seed alone. Those 8 independent draws are correlated via
    the Cholesky lower-triangular factor of market_assumptions.correlation_matrix
    (decomposed once per call, outside every loop -- it's the same matrix
    for every path/year), then scaled by each asset class's own mean/std.
    Raw per-asset-class returns are stored, never pre-blended -- blending
    by a pool's own active glide-path weights happens later, inside
    run_plan_projection() (comparison.allocation.blended_pool_return()).

    This is the direct N-asset generalization of the pre-rp-aev 2-variable
    closed-form bivariate-normal formula (`bond = mean + std*(corr*z1 +
    sqrt(1-corr^2)*z2)` is exactly the 2x2 special case of `L @ z`).

    Raises ValueError if path_count <= 0, or if correlation_matrix is not
    a valid (positive-semi-definite) correlation matrix.
    """
    if path_count <= 0:
        raise ValueError(f"path_count must be positive, got {path_count}")

    lower = cholesky_lower(market_assumptions.correlation_matrix)
    rng = random.Random(seed)

    paths: list[AssetClassReturnPath] = []
    for _ in range(path_count):
        asset_returns_by_year: list[dict[AssetClass, float]] = []
        for _ in range(horizon_years):
            independent_draws = [rng.gauss(0.0, 1.0) for _ in range(_ASSET_CLASS_COUNT)]
            correlated_draws = [
                sum(lower[i][k] * independent_draws[k] for k in range(i + 1)) for i in range(_ASSET_CLASS_COUNT)
            ]
            year_returns: dict[AssetClass, float] = {}
            for index, asset_class in enumerate(ASSET_CLASSES):
                assumptions = market_assumptions.asset_classes[asset_class]
                year_returns[asset_class] = assumptions.mean_real + assumptions.std_real * correlated_draws[index]
            asset_returns_by_year.append(year_returns)
        paths.append(
            AssetClassReturnPath(
                start_plan_year=start_plan_year,
                asset_returns=asset_returns_by_year,
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
) -> list[AssetClassReturnPath]:
    """Generates path_count independent AssetClassReturnPaths via
    moving-block bootstrap resampling from HISTORICAL_RETURNS: repeatedly
    picks a random contiguous block_length-year window from the documented
    historical years, concatenates blocks until horizon_years is reached,
    truncates to exactly horizon_years. Each drawn year's own 8-asset-class
    return dict is used as-is, raw (never blended here) -- blending moves
    to run_plan_projection(), same as the parametric path above. Raises
    ValueError if block_length exceeds the number of documented historical
    years, or if block_length <= 0 or path_count <= 0.
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

    paths: list[AssetClassReturnPath] = []
    for _ in range(path_count):
        asset_returns_by_year: list[dict[AssetClass, float]] = []
        figures_used = []
        while len(asset_returns_by_year) < horizon_years:
            start_index = rng.randrange(0, max_start_index + 1)
            for offset in range(block_length):
                if len(asset_returns_by_year) >= horizon_years:
                    break
                year = documented_years[start_index + offset]
                asset_returns_by_year.append(dict(HISTORICAL_RETURNS.schedule[year]))
                figures_used.append(HISTORICAL_RETURNS.usage_for_year(year))
        paths.append(
            AssetClassReturnPath(
                start_plan_year=start_plan_year,
                asset_returns=asset_returns_by_year,
                generation_mode="historical_bootstrap",
                figures_used=figures_used,
            )
        )
    return paths


def apply_stress_scenario(
    paths: list[AssetClassReturnPath],
    stress: StressScenario,
    horizon_last_plan_year: int,
) -> list[AssetClassReturnPath]:
    """Returns a new list[AssetClassReturnPath] (paths is not mutated)
    with every path's asset_returns overridden, for plan years in
    [stress.start_plan_year, stress.start_plan_year + stress.duration_years),
    so that EVERY one of the 8 asset classes returns exactly
    stress.magnitude that year -- a weighted average of 8 identical values
    is that value, so every pool's own blended return in the stressed
    window becomes exactly stress.magnitude too, reproducing the pre-rp-aev
    pool-level override behavior exactly. Every other year is unchanged;
    generation_mode and figures_used are carried through unchanged. Raises
    ValueError if stress.start_plan_year + stress.duration_years - 1 >
    horizon_last_plan_year.
    """
    window_last_plan_year = stress.start_plan_year + stress.duration_years - 1
    if window_last_plan_year > horizon_last_plan_year:
        raise ValueError(
            f"stress window ends at plan year {window_last_plan_year}, "
            f"beyond the horizon's last plan year {horizon_last_plan_year}"
        )

    stressed_paths: list[AssetClassReturnPath] = []
    for path in paths:
        new_asset_returns = list(path.asset_returns)
        for plan_year in range(stress.start_plan_year, stress.start_plan_year + stress.duration_years):
            index = plan_year - path.start_plan_year
            if 0 <= index < len(new_asset_returns):
                new_asset_returns[index] = {asset_class: stress.magnitude for asset_class in ASSET_CLASSES}
        stressed_paths.append(replace(path, asset_returns=new_asset_returns))
    return stressed_paths
