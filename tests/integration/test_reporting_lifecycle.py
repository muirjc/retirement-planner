"""Integration test: the full quickstart.md walkthrough for
006-reporting-aggregation (summarize one run, summarize comparisons of
both kinds, export to CSV, and confirm unverified figures stay visible
throughout).

See specs/006-reporting-aggregation/quickstart.md — this test exercises
the same four sections.
"""

from retirement_planner.comparison import StrategyConfiguration, compare_roth_conversion_strategies, derive_deterministic_return
from retirement_planner.mechanics import AccountBalances
from retirement_planner.reporting import (
    run_to_csv_text,
    simulation_comparison_to_csv_text,
    summarize_deterministic_comparison,
    summarize_run,
    summarize_simulation_comparison,
)
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions
from retirement_planner.simulation import compare_states, generate_historical_bootstrap_paths, generate_return_paths, run_simulation

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
_REFERENCE_TAX_YEAR = 2026


def _base_run():
    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=1_000, horizon_years=36, start_plan_year=1, seed=42,
    )
    return run_simulation(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, annual_spending_need=110_000, state="FL",
        reference_tax_year=_REFERENCE_TAX_YEAR, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
        strategy=_STRATEGY, return_paths=return_paths, candidate_label="base_case",
    )


def test_step1_summarize_one_simulation_run():
    run = _base_run()

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=_REFERENCE_TAX_YEAR)

    assert summary.candidate_label is None
    assert summary.success_rate == run.success_rate
    assert summary.percentile_bands == run.percentile_bands
    if run.success_rate < 1.0:
        assert summary.median_depletion_age is not None
    else:
        assert summary.median_depletion_age is None
    assert isinstance(summary.unverified_figure_names, list)

    repeat = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=_REFERENCE_TAX_YEAR)
    assert repeat == summary


def test_step2_compare_candidates_both_kinds():
    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=1_000, horizon_years=1, start_plan_year=1, seed=42,
    )
    comparison = compare_states(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, annual_spending_need=110_000, states=["SC", "DE", "FL"],
        reference_tax_year=_REFERENCE_TAX_YEAR, start_plan_year=1, start_tax_year=2026,
        plan_to_age=60,  # single-plan-year horizon -- keeps every state within its documented tax years
        strategy=_STRATEGY, return_paths=return_paths,
    )

    summaries = summarize_simulation_comparison(comparison, household=_HOUSEHOLD, reference_tax_year=_REFERENCE_TAX_YEAR)

    assert len(summaries) == len(comparison.runs) == 3
    for summary, run in zip(summaries, comparison.runs):
        assert summary.candidate_label == run.candidate_label

    deterministic = compare_roth_conversion_strategies(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, annual_spending_need=110_000, state="FL",
        reference_tax_year=_REFERENCE_TAX_YEAR, start_plan_year=1, start_tax_year=2026, plan_to_age=70,
        withdrawal_strategy="rmd_taxable_traditional_roth", claiming_ages={"you": 67, "spouse": 67},
        return_assumption=derive_deterministic_return(_MARKET),
        candidates=[_STRATEGY],
    )
    deterministic_summaries = summarize_deterministic_comparison(
        deterministic, household=_HOUSEHOLD, reference_tax_year=_REFERENCE_TAX_YEAR
    )

    assert len(deterministic_summaries) == 1
    assert deterministic_summaries[0].success_rate is None
    assert deterministic_summaries[0].percentile_bands is None
    assert isinstance(deterministic_summaries[0].ending_balance, float)


def test_step3_export_to_csv():
    run = _base_run()
    return_paths = generate_return_paths(
        market_assumptions=_MARKET, path_count=1_000, horizon_years=1, start_plan_year=1, seed=42,
    )
    comparison = compare_states(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, annual_spending_need=110_000, states=["SC", "DE", "FL"],
        reference_tax_year=_REFERENCE_TAX_YEAR, start_plan_year=1, start_tax_year=2026, plan_to_age=60,
        strategy=_STRATEGY, return_paths=return_paths,
    )

    run_csv = run_to_csv_text(run)
    assert run_csv.splitlines()[0].startswith("plan_year")
    assert len(run_csv.splitlines()) == 1 + len(run.percentile_bands)

    comparison_csv = simulation_comparison_to_csv_text(comparison, household=_HOUSEHOLD, reference_tax_year=_REFERENCE_TAX_YEAR)
    assert len(comparison_csv.splitlines()) == 1 + len(comparison.runs)
    assert all(state in comparison_csv for state in ("SC", "DE", "FL"))


def test_step4_unverified_figures_stay_visible():
    bootstrap_paths = generate_historical_bootstrap_paths(
        market_assumptions=_MARKET, path_count=500, horizon_years=36, start_plan_year=1, seed=42, block_length=10,
    )
    bootstrap_run = run_simulation(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, annual_spending_need=110_000, state="FL",
        reference_tax_year=_REFERENCE_TAX_YEAR, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
        strategy=_STRATEGY, return_paths=bootstrap_paths, candidate_label="historical_bootstrap",
    )
    summary = summarize_run(bootstrap_run, household=_HOUSEHOLD, reference_tax_year=_REFERENCE_TAX_YEAR)

    assert "historical_annual_real_returns" in summary.unverified_figure_names
    assert len(summary.unverified_figure_names) == len(set(summary.unverified_figure_names))

    csv_text = run_to_csv_text(bootstrap_run)
    assert "has_unverified_figure" in csv_text.splitlines()[0]
