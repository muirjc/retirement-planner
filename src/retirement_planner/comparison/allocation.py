"""Per-pool blended-return math for the 8-asset-class portfolio model
(rp-aev). Mirrors mechanics/cash_reserve.py's own precedent: a tiny,
standalone pure function, no classes -- run_plan_projection() calls it
once per pool per plan year and holds any derived state itself.

Why this one function is the entire new math primitive: because every
pool is rebalanced to its own target weights every plan year (no drift
carried forward), a pool's blended return this year is exactly the
weighted average of this year's 8 raw asset-class returns, using
whichever glide-path period is active. No real per-asset-class dollar
sub-balance ever needs to be tracked for this to be correct -- see
run_plan_projection()'s own docstring for the full rationale.
"""

from __future__ import annotations

from retirement_planner.scenario import ASSET_CLASSES, AssetClass


def blended_pool_return(asset_returns: dict[AssetClass, float], weights: dict[AssetClass, float]) -> float:
    return sum(weights[asset_class] * asset_returns[asset_class] for asset_class in ASSET_CLASSES)
