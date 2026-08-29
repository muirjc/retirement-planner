"""Unit tests for retirement_planner.simulation.returns: parametric
correlated-normal return generation (US1), historical-bootstrap resampling
(US3), and sequence-of-returns stress overlay (US4).
"""

import math
import random

import pytest

from retirement_planner.scenario import MarketAssumptions
from retirement_planner.simulation.models import ReturnPath, StressScenario

MARKET = MarketAssumptions(
    equity_allocation=0.60,
    equity_return_mean_real=0.065,
    equity_return_std_real=0.17,
    bond_allocation=0.40,
    bond_return_mean_real=0.015,
    bond_return_std_real=0.06,
    correlation=-0.10,
)


def _expected_blended_return(z1: float, z2: float, market: MarketAssumptions) -> float:
    equity_return = market.equity_return_mean_real + market.equity_return_std_real * z1
    bond_return = market.bond_return_mean_real + market.bond_return_std_real * (
        market.correlation * z1 + math.sqrt(1 - market.correlation**2) * z2
    )
    return market.equity_allocation * equity_return + market.bond_allocation * bond_return


# --- generate_return_paths() (US1, research.md §3) ---


def test_correlated_normal_draws_match_manual_computation_in_fixed_order():
    from retirement_planner.simulation.returns import generate_return_paths

    seed = 42
    paths = generate_return_paths(
        market_assumptions=MARKET, path_count=2, horizon_years=3, start_plan_year=1, seed=seed
    )

    # Manually replicate the documented RNG consumption order: path 0's
    # years in order, then path 1's; two .gauss() calls per year, z1
    # before z2 (research.md §3).
    rng = random.Random(seed)
    expected_path0 = []
    expected_path1 = []
    for _ in range(3):
        z1, z2 = rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)
        expected_path0.append(_expected_blended_return(z1, z2, MARKET))
    for _ in range(3):
        z1, z2 = rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)
        expected_path1.append(_expected_blended_return(z1, z2, MARKET))

    assert paths[0].annual_returns == pytest.approx(expected_path0)
    assert paths[1].annual_returns == pytest.approx(expected_path1)
    assert paths[0].generation_mode == "parametric"
    assert paths[0].figures_used == []
    assert paths[0].start_plan_year == 1


def test_generate_return_paths_rejects_non_positive_path_count():
    from retirement_planner.simulation.returns import generate_return_paths

    with pytest.raises(ValueError):
        generate_return_paths(market_assumptions=MARKET, path_count=0, horizon_years=5, start_plan_year=1, seed=1)
    with pytest.raises(ValueError):
        generate_return_paths(market_assumptions=MARKET, path_count=-1, horizon_years=5, start_plan_year=1, seed=1)


def test_generate_return_paths_is_reproducible_under_identical_seed():
    from retirement_planner.simulation.returns import generate_return_paths

    first = generate_return_paths(market_assumptions=MARKET, path_count=50, horizon_years=10, start_plan_year=1, seed=7)
    second = generate_return_paths(market_assumptions=MARKET, path_count=50, horizon_years=10, start_plan_year=1, seed=7)

    assert first == second


# --- generate_historical_bootstrap_paths() (US3, research.md §4) ---


def test_historical_bootstrap_paths_are_built_from_contiguous_blocks():
    from retirement_planner.simulation.historical_data import HISTORICAL_RETURNS
    from retirement_planner.simulation.returns import generate_historical_bootstrap_paths

    documented_years = sorted(HISTORICAL_RETURNS.schedule.keys())
    block_length = 10
    paths = generate_historical_bootstrap_paths(
        market_assumptions=MARKET, path_count=5, horizon_years=25, start_plan_year=1, seed=3,
        block_length=block_length,
    )

    for path in paths:
        assert path.generation_mode == "historical_bootstrap"
        assert len(path.annual_returns) == 25
        assert len(path.figures_used) > 0
        assert all(not usage.verified for usage in path.figures_used)

    # Every block of `block_length` consecutive returns in a path must be
    # explainable as one contiguous run of documented historical years
    # (not independently resampled individual years) -- verify by
    # reconstructing candidate blended values for every documented
    # contiguous block and confirming each path's first block matches one
    # of them exactly, in order.
    def _blend(year):
        equity, bond = HISTORICAL_RETURNS.schedule[year]
        return MARKET.equity_allocation * equity + MARKET.bond_allocation * bond

    candidate_blocks = [
        [_blend(y) for y in documented_years[i : i + block_length]]
        for i in range(0, len(documented_years) - block_length + 1)
    ]
    for path in paths:
        first_block = path.annual_returns[:block_length]
        assert any(
            all(a == pytest.approx(b) for a, b in zip(first_block, candidate))
            for candidate in candidate_blocks
        )


def test_generate_historical_bootstrap_paths_is_reproducible_under_identical_seed():
    from retirement_planner.simulation.returns import generate_historical_bootstrap_paths

    first = generate_historical_bootstrap_paths(
        market_assumptions=MARKET, path_count=10, horizon_years=20, start_plan_year=1, seed=11, block_length=5
    )
    second = generate_historical_bootstrap_paths(
        market_assumptions=MARKET, path_count=10, horizon_years=20, start_plan_year=1, seed=11, block_length=5
    )

    assert first == second


def test_generate_historical_bootstrap_paths_rejects_block_length_exceeding_documented_years():
    from retirement_planner.simulation.historical_data import HISTORICAL_RETURNS
    from retirement_planner.simulation.returns import generate_historical_bootstrap_paths

    too_long = len(HISTORICAL_RETURNS.schedule) + 1
    with pytest.raises(ValueError):
        generate_historical_bootstrap_paths(
            market_assumptions=MARKET, path_count=1, horizon_years=5, start_plan_year=1, seed=1,
            block_length=too_long,
        )


def test_generate_historical_bootstrap_paths_rejects_non_positive_block_length():
    from retirement_planner.simulation.returns import generate_historical_bootstrap_paths

    with pytest.raises(ValueError):
        generate_historical_bootstrap_paths(
            market_assumptions=MARKET, path_count=1, horizon_years=5, start_plan_year=1, seed=1, block_length=0
        )


# --- apply_stress_scenario() (US4, research.md § StressScenario) ---


def test_apply_stress_scenario_overrides_only_the_configured_window():
    from retirement_planner.simulation.returns import apply_stress_scenario

    base_paths = [
        ReturnPath(start_plan_year=1, annual_returns=[0.05, 0.06, 0.07, 0.08], generation_mode="parametric", figures_used=[]),
    ]
    stress = StressScenario(magnitude=-0.30, duration_years=2, start_plan_year=2)

    stressed_paths = apply_stress_scenario(base_paths, stress, horizon_last_plan_year=4)

    assert stressed_paths[0].annual_returns == [0.05, -0.30, -0.30, 0.08]
    assert stressed_paths[0].generation_mode == base_paths[0].generation_mode
    assert stressed_paths[0].figures_used == base_paths[0].figures_used
    # Non-mutating: the original paths list is untouched.
    assert base_paths[0].annual_returns == [0.05, 0.06, 0.07, 0.08]


def test_apply_stress_scenario_at_different_start_years_changes_run_simulation_outcome():
    from retirement_planner.comparison import StrategyConfiguration
    from retirement_planner.mechanics import AccountBalances
    from retirement_planner.scenario import Household, HouseholdMember
    from retirement_planner.simulation.monte_carlo import run_simulation
    from retirement_planner.simulation.returns import apply_stress_scenario

    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=90, ss_claim_age=99, ss_annual_benefit=0)],
    )
    accounts = AccountBalances(traditional=0, roth=0, taxable=100)
    strategy = StrategyConfiguration(
        label="test", withdrawal_strategy="rmd_taxable_traditional_roth", conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None, conversion_window=None, claiming_ages={"you": 99},
    )
    base_paths = [
        ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0], generation_mode="parametric", figures_used=[]),
    ]
    common_kwargs = dict(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 1.0},
        annual_spending_need=50, state="FL",
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=91, strategy=strategy,
    )

    shock_year1 = apply_stress_scenario(
        base_paths, StressScenario(magnitude=-0.50, duration_years=1, start_plan_year=1), horizon_last_plan_year=2
    )
    shock_year2 = apply_stress_scenario(
        base_paths, StressScenario(magnitude=-0.50, duration_years=1, start_plan_year=2), horizon_last_plan_year=2
    )

    run_year1_shock = run_simulation(**common_kwargs, return_paths=shock_year1, candidate_label="shock1")
    run_year2_shock = run_simulation(**common_kwargs, return_paths=shock_year2, candidate_label="shock2")

    # A shock in year 1 shrinks year 2's starting balance (sequence-of-
    # returns risk); a shock in year 2 (the last plan year) cannot affect
    # any subsequent year's starting balance, so the two runs' success
    # rates are free to (and here, do) differ.
    assert run_year1_shock.success_rate != run_year2_shock.success_rate


def test_apply_stress_scenario_rejects_window_extending_beyond_horizon():
    from retirement_planner.simulation.returns import apply_stress_scenario

    base_paths = [
        ReturnPath(start_plan_year=1, annual_returns=[0.05, 0.06, 0.07], generation_mode="parametric", figures_used=[]),
    ]
    stress = StressScenario(magnitude=-0.30, duration_years=2, start_plan_year=2)

    with pytest.raises(ValueError):
        apply_stress_scenario(base_paths, stress, horizon_last_plan_year=2)
