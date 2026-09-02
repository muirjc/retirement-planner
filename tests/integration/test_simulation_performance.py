"""Mandatory performance benchmark (plan.md Constitution Check's Performance
Budget gate, research.md §7, SC-003, tasks.md T051): the reference-scale
simulation -- 3,000-5,000 Monte Carlo paths, up to the currently-registered
candidate states -- MUST complete in well under a minute on standard
hardware. This feature is not considered done until this test passes.

Empirical finding during implementation (research.md §7's addendum): the
per-plan-year mechanics/tax chain this feature invokes costs well under a
millisecond, not the tens-of-milliseconds the original conservative budget
assumed -- so the reference scale comfortably meets the budget running
*serially*; ProcessPoolExecutor's own IPC overhead dominates and actually
regresses wall-clock time at this per-task cost unless dispatch is reserved
for much larger path counts. `_PARALLEL_DISPATCH_THRESHOLD` in monte_carlo.py
is set accordingly -- this benchmark exercises that real, tuned threshold,
not an artificially forced code path.
"""

import time

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions
from retirement_planner.simulation import (
    SURVIVAL_TABLE,
    compare_states,
    generate_death_age_draws,
    generate_return_paths,
    run_simulation,
)

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
_STRATEGY = StrategyConfiguration(
    label="fill_to_22_pct_bracket",
    withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy="fill_to_bracket",
    conversion_bracket_ceiling_or_amount=206_700,
    conversion_window=(2028, 2034),
    claiming_ages={"you": 67, "spouse": 67},
)
_HORIZON_YEARS = 95 - 60 + 1  # 36 plan years, matching quickstart.md's reference profile
_COMMON_KWARGS = dict(
    household=_HOUSEHOLD,
    accounts=_ACCOUNTS,
    traditional_ownership_shares={"you": 0.75, "spouse": 0.25},
    annual_spending_need=110_000,
    reference_tax_year=2026,
    start_plan_year=1,
    start_tax_year=2026,
    plan_to_age=95,
    strategy=_STRATEGY,
)
_REFERENCE_PATH_COUNT = 5_000
_BUDGET_SECONDS = 60.0


def test_single_configuration_reference_scale_completes_well_under_a_minute():
    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=_REFERENCE_PATH_COUNT, horizon_years=_HORIZON_YEARS,
        start_plan_year=1, seed=42,
    )

    start = time.perf_counter()
    run = run_simulation(**_COMMON_KWARGS, state="FL", return_paths=return_paths, candidate_label="base_case")
    elapsed = time.perf_counter() - start

    assert len(run.path_results) == _REFERENCE_PATH_COUNT
    assert elapsed < _BUDGET_SECONDS, (
        f"{_REFERENCE_PATH_COUNT}-path single-configuration simulation took {elapsed:.1f}s, "
        f"exceeding the {_BUDGET_SECONDS:.0f}s budget (SC-003, Constitution Principle VI)"
    )


def test_state_comparison_reference_scale_completes_well_under_a_minute():
    # Every state currently registered in 002-tax-calculation-engine's
    # STATE_MODULES; DE's bracket table only documents 2026 (002's own
    # scope), so a single-plan-year horizon keeps every candidate within
    # its documented years for this benchmark.
    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=_REFERENCE_PATH_COUNT, horizon_years=1, start_plan_year=1, seed=42,
    )
    single_year_kwargs = {**_COMMON_KWARGS, "plan_to_age": 60}

    start = time.perf_counter()
    comparison = compare_states(**single_year_kwargs, states=["SC", "DE", "FL"], return_paths=return_paths)
    elapsed = time.perf_counter() - start

    assert len(comparison.runs) == 3
    assert all(len(run.path_results) == _REFERENCE_PATH_COUNT for run in comparison.runs)
    assert elapsed < _BUDGET_SECONDS, (
        f"{_REFERENCE_PATH_COUNT}-path x 3-state comparison took {elapsed:.1f}s, "
        f"exceeding the {_BUDGET_SECONDS:.0f}s budget (SC-003, Constitution Principle VI)"
    )


def test_reference_scale_with_probabilistic_death_draws_completes_well_under_a_minute():
    """023-probabilistic-death-draws (rp-vgv) FR-012/SC-006: confirms the
    constitution's Performance Budget gate empirically for this new
    capability, rather than assuming it away (research.md §8) -- same
    reference-scale single-configuration profile as
    test_single_configuration_reference_scale_completes_well_under_a_minute
    above, with survival_curves and death_year_draws both supplied."""
    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=_REFERENCE_PATH_COUNT, horizon_years=_HORIZON_YEARS,
        start_plan_year=1, seed=42,
    )
    survival_curves = {"you": SURVIVAL_TABLE["primary"], "spouse": SURVIVAL_TABLE["spouse"]}
    death_year_draws = generate_death_age_draws(
        household=_HOUSEHOLD, survival_curves=survival_curves, path_count=_REFERENCE_PATH_COUNT, seed=99,
    )

    start = time.perf_counter()
    run = run_simulation(
        **_COMMON_KWARGS, state="FL", return_paths=return_paths, candidate_label="base_case",
        survival_curves=survival_curves, death_year_draws=death_year_draws,
    )
    elapsed = time.perf_counter() - start

    assert len(run.path_results) == _REFERENCE_PATH_COUNT
    assert elapsed < _BUDGET_SECONDS, (
        f"{_REFERENCE_PATH_COUNT}-path single-configuration simulation with probabilistic death draws "
        f"took {elapsed:.1f}s, exceeding the {_BUDGET_SECONDS:.0f}s budget (FR-012, SC-006, "
        "Constitution Principle VI)"
    )
