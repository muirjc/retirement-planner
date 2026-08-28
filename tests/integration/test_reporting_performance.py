"""Performance check (plan.md Performance Goals, SC-005): summarizing and
exporting a reference-scale (5,000-path) SimulationRun MUST add no
perceptible delay beyond the simulation itself completing. Unlike
005-simulation-engine, this is not a flagged risk -- every operation here
is a single linear pass over already-computed data (plan.md Constitution
Check) -- this test confirms that expectation empirically rather than
just asserting it.
"""

import time

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.reporting import run_to_csv_text, summarize_run
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions
from retirement_planner.simulation import generate_return_paths, run_simulation

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
_REFERENCE_PATH_COUNT = 5_000
_BUDGET_SECONDS = 1.0  # "no perceptible added delay" -- generous relative to
                        # the sub-millisecond cost plan.md's Performance
                        # Goals project for a single O(paths) pass


def test_summarize_and_export_add_no_perceptible_delay_at_reference_scale():
    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=_REFERENCE_PATH_COUNT, horizon_years=36, start_plan_year=1, seed=42,
    )
    run = run_simulation(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, annual_spending_need=110_000, state="FL",
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
        strategy=_STRATEGY, return_paths=return_paths, candidate_label="base_case",
    )

    start = time.perf_counter()
    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)
    csv_text = run_to_csv_text(run)
    elapsed = time.perf_counter() - start

    assert len(run.path_results) == _REFERENCE_PATH_COUNT
    assert isinstance(summary.median_lifetime_tax_paid, float)
    assert len(csv_text.splitlines()) == 1 + len(run.percentile_bands)
    assert elapsed < _BUDGET_SECONDS, (
        f"summarize_run()+run_to_csv_text() on a {_REFERENCE_PATH_COUNT}-path run took {elapsed:.3f}s, "
        f"exceeding the {_BUDGET_SECONDS:.1f}s budget (SC-005)"
    )
