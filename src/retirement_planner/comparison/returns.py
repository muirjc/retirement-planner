"""Deterministic return derivation (FR-003).

Stands in for genuine multi-path Monte Carlo simulation, which is deferred
to the future Simulation Engine feature (§3.5) — see
specs/004-strategy-comparison-layer/research.md §1.
"""

from __future__ import annotations

from retirement_planner.scenario import MarketAssumptions

from .models import DeterministicReturnAssumption


def derive_deterministic_return(market_assumptions: MarketAssumptions) -> DeterministicReturnAssumption:
    """Returns the allocation-weighted blend of equity_return_mean_real and
    bond_return_mean_real (FR-003, research.md §1). Ignores
    equity_return_std_real, bond_return_std_real, and correlation entirely
    — this is a fixed value, not a distribution to sample from.
    """
    blended_return = (
        market_assumptions.equity_allocation * market_assumptions.equity_return_mean_real
        + market_assumptions.bond_allocation * market_assumptions.bond_return_mean_real
    )
    return DeterministicReturnAssumption(annual_real_return=blended_return)
