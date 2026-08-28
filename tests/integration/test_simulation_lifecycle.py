"""Integration test: the full quickstart.md walkthrough for
005-simulation-engine (probabilistic Monte Carlo simulation, paired-draw
comparison including the state axis, historical-bootstrap generation,
sequence-of-returns stress scenarios, and survival-adjusted scoring).

See specs/005-simulation-engine/quickstart.md — this test exercises the
same five sections, using "FL"/"SC"/"DE" as the states (already implemented
by 002-tax-calculation-engine's STATE_MODULES; "GA", used as an example in
quickstart.md's prose, is not yet an implemented state module — mirrors
004's own test_comparison_lifecycle.py adaptation).
"""

import pytest

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions

_HOUSEHOLD = Household(
    filing_status="married_filing_jointly",
    members=[
        HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=32_000),
        HouseholdMember(person_name="spouse", current_age=58, ss_claim_age=67, ss_annual_benefit=24_000),
    ],
)
_ACCOUNTS = AccountBalances(traditional=1_500_000, roth=400_000, taxable=200_000)
_MARKET = MarketAssumptions(
    equity_allocation=0.60,
    equity_return_mean_real=0.065,
    equity_return_std_real=0.17,
    bond_allocation=0.40,
    bond_return_mean_real=0.015,
    bond_return_std_real=0.06,
    correlation=-0.10,
)
_HORIZON_YEARS = 95 - 60 + 1
_COMMON_KWARGS = dict(
    household=_HOUSEHOLD,
    accounts=_ACCOUNTS,
    annual_spending_need=110_000,
    reference_tax_year=2026,
    start_plan_year=1,
    start_tax_year=2026,
    plan_to_age=95,
)
_STRATEGY = StrategyConfiguration(
    label="fill_to_22_pct_bracket",
    withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy="fill_to_bracket",
    conversion_bracket_ceiling_or_amount=206_700,
    conversion_window=(2028, 2034),
    claiming_ages={"you": 67, "spouse": 67},
)

# A modest path count keeps this integration test fast; T051's dedicated
# performance benchmark exercises the full 3,000-5,000-path reference scale.
_PATH_COUNT = 200


def test_step1_run_a_probabilistic_monte_carlo_simulation():
    from retirement_planner.simulation import generate_return_paths, run_simulation

    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=_PATH_COUNT, horizon_years=_HORIZON_YEARS,
        start_plan_year=1, seed=42,
    )
    assert len(return_paths) == _PATH_COUNT

    run = run_simulation(
        **_COMMON_KWARGS, state="FL", strategy=_STRATEGY, return_paths=return_paths, candidate_label="base_case",
    )

    assert len(run.path_results) == _PATH_COUNT
    assert 0.0 <= run.success_rate <= 1.0
    assert len(run.percentile_bands) == _HORIZON_YEARS

    repeat = run_simulation(
        **_COMMON_KWARGS, state="FL", strategy=_STRATEGY, return_paths=return_paths, candidate_label="base_case",
    )
    assert repeat.success_rate == run.success_rate
    assert repeat.percentile_bands == run.percentile_bands


def test_step2_compare_states_using_shared_paired_draw_set():
    from retirement_planner.simulation import compare_states, generate_return_paths

    # SC and DE's bracket tables currently document only 2026-2027 and 2026
    # respectively (002's own illustrative-data scope, per their SourcedFigure
    # schedules) -- a single-plan-year horizon (tax_year 2026 only) keeps
    # this comparison within every candidate state's documented years.
    single_year_kwargs = {**_COMMON_KWARGS, "plan_to_age": 60}
    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=_PATH_COUNT, horizon_years=1, start_plan_year=1, seed=42,
    )

    comparison = compare_states(
        **single_year_kwargs, states=["SC", "DE", "FL"], strategy=_STRATEGY, return_paths=return_paths,
    )

    assert comparison.axis == "state"
    assert len(comparison.runs) == 3
    assert comparison.return_paths is return_paths

    # Value equality, not object identity: at this path count the
    # 200-path run exceeds the parallel-dispatch threshold, and a
    # worker-process round trip through pickling necessarily produces a
    # deserialized copy rather than the exact same object (the structural
    # pairing guarantee is that every candidate consumes the identical
    # *values*, path-for-path -- see the serial-dispatch `is` checks in
    # tests/unit/simulation/test_compare.py for the below-threshold case).
    for run in comparison.runs:
        assert run.path_results[0].return_assumption == return_paths[0]


def test_step3_historical_bootstrap_return_generation():
    from retirement_planner.simulation import generate_historical_bootstrap_paths, run_simulation

    bootstrap_paths = generate_historical_bootstrap_paths(
        market_assumptions=_MARKET, path_count=_PATH_COUNT, horizon_years=_HORIZON_YEARS,
        start_plan_year=1, seed=42, block_length=10,
    )
    assert len(bootstrap_paths) == _PATH_COUNT
    assert all(p.generation_mode == "historical_bootstrap" for p in bootstrap_paths)
    assert all(len(p.figures_used) > 0 for p in bootstrap_paths)

    bootstrap_run = run_simulation(
        **_COMMON_KWARGS, state="FL", strategy=_STRATEGY, return_paths=bootstrap_paths,
        candidate_label="historical_bootstrap",
    )
    assert 0.0 <= bootstrap_run.success_rate <= 1.0

    repeat_bootstrap = generate_historical_bootstrap_paths(
        market_assumptions=_MARKET, path_count=_PATH_COUNT, horizon_years=_HORIZON_YEARS,
        start_plan_year=1, seed=42, block_length=10,
    )
    assert repeat_bootstrap == bootstrap_paths


def test_step4_configurable_stress_scenario():
    from retirement_planner.simulation import StressScenario, apply_stress_scenario, generate_return_paths, run_simulation

    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=_PATH_COUNT, horizon_years=_HORIZON_YEARS,
        start_plan_year=1, seed=42,
    )

    early_shock = StressScenario(magnitude=-0.30, duration_years=2, start_plan_year=1)
    late_shock = StressScenario(magnitude=-0.30, duration_years=2, start_plan_year=20)

    early_paths = apply_stress_scenario(return_paths, early_shock, horizon_last_plan_year=_HORIZON_YEARS)
    late_paths = apply_stress_scenario(return_paths, late_shock, horizon_last_plan_year=_HORIZON_YEARS)

    assert early_paths[0].annual_returns[0] == -0.30
    assert early_paths[0].annual_returns[2] == return_paths[0].annual_returns[2]

    early_run = run_simulation(
        **_COMMON_KWARGS, state="FL", strategy=_STRATEGY, return_paths=early_paths, candidate_label="shock_year_1",
    )
    late_run = run_simulation(
        **_COMMON_KWARGS, state="FL", strategy=_STRATEGY, return_paths=late_paths, candidate_label="shock_year_20",
    )
    assert isinstance(early_run.success_rate, float)
    assert isinstance(late_run.success_rate, float)


def test_step5_survival_adjusted_success_rate():
    from retirement_planner.simulation import SURVIVAL_TABLE, generate_return_paths, run_simulation

    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=_PATH_COUNT, horizon_years=_HORIZON_YEARS,
        start_plan_year=1, seed=42,
    )

    run = run_simulation(
        **_COMMON_KWARGS, state="FL", strategy=_STRATEGY, return_paths=return_paths, candidate_label="base_case",
    )
    survival_run = run_simulation(
        **_COMMON_KWARGS, state="FL", strategy=_STRATEGY, return_paths=return_paths,
        candidate_label="base_case_survival",
        survival_curves={"you": SURVIVAL_TABLE["primary"], "spouse": SURVIVAL_TABLE["spouse"]},
    )

    assert survival_run.success_rate == run.success_rate
    assert survival_run.survival_adjusted_success_rate is not None
    assert survival_run.survival_adjusted_success_rate >= survival_run.success_rate
    assert run.survival_adjusted_success_rate is None
