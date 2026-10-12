"""Deterministic return derivation.

rp-aev: no longer blends anything itself -- blending by a pool's own
active glide-path weights happens separately, per plan year, inside
run_plan_projection() (allocation.py::blended_pool_return()). This
function just hands back each asset class's own mean_real unchanged,
satisfying AssetClassReturnSchedule with no variance to sample from
(there's nothing to sample under the Deterministic engine).
"""

from __future__ import annotations

from retirement_planner.scenario import ASSET_CLASSES, MarketAssumptions

from .models import DeterministicAssetClassReturnAssumption


def derive_deterministic_return(market_assumptions: MarketAssumptions) -> DeterministicAssetClassReturnAssumption:
    return DeterministicAssetClassReturnAssumption(
        asset_class_means={
            asset_class: market_assumptions.asset_classes[asset_class].mean_real for asset_class in ASSET_CLASSES
        }
    )
