"""Unit tests for derive_deterministic_return() (Foundational)."""

import pytest

from retirement_planner.comparison import derive_deterministic_return
from retirement_planner.scenario import MarketAssumptions


def test_blend_is_allocation_weighted():
    market = MarketAssumptions(
        equity_allocation=0.60,
        equity_return_mean_real=0.065,
        equity_return_std_real=0.17,
        bond_allocation=0.40,
        bond_return_mean_real=0.015,
        bond_return_std_real=0.06,
        correlation=-0.10,
    )
    result = derive_deterministic_return(market)
    assert result.annual_real_return == pytest.approx(0.60 * 0.065 + 0.40 * 0.015)


def test_std_and_correlation_are_ignored():
    market_a = MarketAssumptions(
        equity_allocation=0.60,
        equity_return_mean_real=0.065,
        equity_return_std_real=0.05,
        bond_allocation=0.40,
        bond_return_mean_real=0.015,
        bond_return_std_real=0.01,
        correlation=0.0,
    )
    market_b = MarketAssumptions(
        equity_allocation=0.60,
        equity_return_mean_real=0.065,
        equity_return_std_real=0.99,
        bond_allocation=0.40,
        bond_return_mean_real=0.015,
        bond_return_std_real=0.99,
        correlation=0.99,
    )
    assert derive_deterministic_return(market_a) == derive_deterministic_return(market_b)


def test_all_equity_allocation_uses_only_equity_mean():
    market = MarketAssumptions(
        equity_allocation=1.0,
        equity_return_mean_real=0.07,
        equity_return_std_real=0.17,
        bond_allocation=0.0,
        bond_return_mean_real=0.02,
        bond_return_std_real=0.06,
        correlation=0.0,
    )
    result = derive_deterministic_return(market)
    assert result.annual_real_return == pytest.approx(0.07)
