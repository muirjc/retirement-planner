"""Unit tests for retirement_planner.simulation.returns: parametric
correlated-normal return generation (8 asset classes, rp-aev),
historical-bootstrap resampling, and sequence-of-returns stress overlay.
"""

import random

import pytest

from retirement_planner.scenario import ASSET_CLASSES, DEFAULT_MARKET_ASSUMPTIONS, cholesky_lower
from retirement_planner.simulation.models import AssetClassReturnPath, StressScenario

MARKET = DEFAULT_MARKET_ASSUMPTIONS
_N = len(ASSET_CLASSES)


def _expected_asset_returns(independent_draws: list[float], market) -> dict:
    lower = cholesky_lower(market.correlation_matrix)
    correlated = [sum(lower[i][k] * independent_draws[k] for k in range(i + 1)) for i in range(_N)]
    return {
        asset_class: market.asset_classes[asset_class].mean_real + market.asset_classes[asset_class].std_real * correlated[index]
        for index, asset_class in enumerate(ASSET_CLASSES)
    }


# --- generate_return_paths() (8-asset correlated draw) ---


def test_correlated_draws_match_manual_computation_in_fixed_order():
    from retirement_planner.simulation.returns import generate_return_paths

    seed = 42
    paths = generate_return_paths(
        market_assumptions=MARKET, path_count=2, horizon_years=3, start_plan_year=1, seed=seed
    )

    # Manually replicate the documented RNG consumption order: path 0's
    # years in order, then path 1's; 8 .gauss() calls per year, in
    # ASSET_CLASSES order.
    rng = random.Random(seed)
    expected_path0 = []
    expected_path1 = []
    for _ in range(3):
        draws = [rng.gauss(0.0, 1.0) for _ in range(_N)]
        expected_path0.append(_expected_asset_returns(draws, MARKET))
    for _ in range(3):
        draws = [rng.gauss(0.0, 1.0) for _ in range(_N)]
        expected_path1.append(_expected_asset_returns(draws, MARKET))

    for year_index in range(3):
        for asset_class in ASSET_CLASSES:
            assert paths[0].asset_returns[year_index][asset_class] == pytest.approx(expected_path0[year_index][asset_class])
            assert paths[1].asset_returns[year_index][asset_class] == pytest.approx(expected_path1[year_index][asset_class])
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


def test_generate_return_paths_reproduces_the_configured_correlation_structure():
    """Property test for the Cholesky transform: over enough draws, the
    empirical correlation between two asset classes' own return series
    should approximate the configured correlation_matrix entry."""
    from retirement_planner.simulation.returns import generate_return_paths

    paths = generate_return_paths(market_assumptions=MARKET, path_count=1, horizon_years=20_000, start_plan_year=1, seed=99)
    us_large = [year["us_large"] for year in paths[0].asset_returns]
    aggregate_bond = [year["aggregate_bond"] for year in paths[0].asset_returns]

    mean_a = sum(us_large) / len(us_large)
    mean_b = sum(aggregate_bond) / len(aggregate_bond)
    cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(us_large, aggregate_bond)) / len(us_large)
    std_a = (sum((a - mean_a) ** 2 for a in us_large) / len(us_large)) ** 0.5
    std_b = (sum((b - mean_b) ** 2 for b in aggregate_bond) / len(aggregate_bond)) ** 0.5
    empirical_correlation = cov / (std_a * std_b)

    configured_correlation = MARKET.correlation_matrix[ASSET_CLASSES.index("us_large")][ASSET_CLASSES.index("aggregate_bond")]
    assert empirical_correlation == pytest.approx(configured_correlation, abs=0.03)


# --- generate_historical_bootstrap_paths() ---


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
        assert len(path.asset_returns) == 25
        assert len(path.figures_used) > 0
        assert all(not usage.verified for usage in path.figures_used)
        assert all(set(year.keys()) == set(ASSET_CLASSES) for year in path.asset_returns)

    # Every block of `block_length` consecutive years in a path must be
    # explainable as one contiguous run of documented historical years
    # (not independently resampled individual years) -- verify by
    # reconstructing every documented contiguous block's own us_large
    # series and confirming each path's first block matches one of them
    # exactly, in order.
    candidate_blocks = [
        [HISTORICAL_RETURNS.schedule[y]["us_large"] for y in documented_years[i : i + block_length]]
        for i in range(0, len(documented_years) - block_length + 1)
    ]
    for path in paths:
        first_block = [year["us_large"] for year in path.asset_returns[:block_length]]
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


# --- apply_stress_scenario() ---


def test_apply_stress_scenario_overrides_only_the_configured_window():
    from retirement_planner.simulation.returns import apply_stress_scenario

    base_paths = [
        AssetClassReturnPath(
            start_plan_year=1,
            asset_returns=[{ac: rate for ac in ASSET_CLASSES} for rate in (0.05, 0.06, 0.07, 0.08)],
            generation_mode="parametric",
            figures_used=[],
        ),
    ]
    stress = StressScenario(magnitude=-0.30, duration_years=2, start_plan_year=2)

    stressed_paths = apply_stress_scenario(base_paths, stress, horizon_last_plan_year=4)

    assert stressed_paths[0].asset_returns[0] == {ac: 0.05 for ac in ASSET_CLASSES}
    assert stressed_paths[0].asset_returns[1] == {ac: -0.30 for ac in ASSET_CLASSES}
    assert stressed_paths[0].asset_returns[2] == {ac: -0.30 for ac in ASSET_CLASSES}
    assert stressed_paths[0].asset_returns[3] == {ac: 0.08 for ac in ASSET_CLASSES}
    assert stressed_paths[0].generation_mode == base_paths[0].generation_mode
    assert stressed_paths[0].figures_used == base_paths[0].figures_used
    # Non-mutating: the original paths list is untouched.
    assert base_paths[0].asset_returns[1] == {ac: 0.06 for ac in ASSET_CLASSES}


def test_apply_stress_scenario_at_different_start_years_changes_run_simulation_outcome():
    from retirement_planner.comparison import StrategyConfiguration
    from retirement_planner.mechanics import AccountBalances
    from retirement_planner.scenario import AllocationPeriod, AllocationSchedule, Household, HouseholdMember
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
    even_schedule = AllocationSchedule(periods=[AllocationPeriod(start_plan_year=1, weights={ac: 1.0 / 8 for ac in ASSET_CLASSES})])
    base_paths = [
        AssetClassReturnPath(
            start_plan_year=1,
            asset_returns=[{ac: 0.0 for ac in ASSET_CLASSES}, {ac: 0.0 for ac in ASSET_CLASSES}],
            generation_mode="parametric",
            figures_used=[],
        ),
    ]
    common_kwargs = dict(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 1.0},
        annual_spending_need=50, state="FL",
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=91, strategy=strategy,
        taxable_allocation_schedule=even_schedule, traditional_allocation_schedule=even_schedule,
        roth_allocation_schedule=even_schedule,
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
        AssetClassReturnPath(
            start_plan_year=1,
            asset_returns=[{ac: rate for ac in ASSET_CLASSES} for rate in (0.05, 0.06, 0.07)],
            generation_mode="parametric",
            figures_used=[],
        ),
    ]
    stress = StressScenario(magnitude=-0.30, duration_years=2, start_plan_year=2)

    with pytest.raises(ValueError):
        apply_stress_scenario(base_paths, stress, horizon_last_plan_year=2)
