"""Runnable example: drives the full 001->002->003->004->005 pipeline
against the source document's reference use case
(docs/initial_requirement.md §2/§6) and prints answers to the tool's three
core questions (§1) -- longevity, tax optimization, and location
comparison. There is no CLI or notebook entry point yet (see
docs/remaining_scope.md §2), so this script is the closest thing to
"running the tool" that currently exists; it also doubles as the first
actual execution of the reference scenario (docs/remaining_scope.md §4
item 4).

Usage:
    python examples/reference_scenario.py

Requires the package installed (editable is fine): pip install -e .
"""

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions
from retirement_planner.simulation import (
    compare_roth_conversion_strategies,
    compare_states,
    generate_return_paths,
    run_simulation,
)


def main() -> None:
    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=32_000),
            HouseholdMember(person_name="spouse", current_age=58, ss_claim_age=67, ss_annual_benefit=24_000),
        ],
    )
    accounts = AccountBalances(traditional=1_500_000, roth=400_000, taxable=200_000)
    market = MarketAssumptions(
        equity_allocation=0.60, equity_return_mean_real=0.065, equity_return_std_real=0.17,
        bond_allocation=0.40, bond_return_mean_real=0.015, bond_return_std_real=0.06,
        correlation=-0.10,
    )
    plan_to_age = 95
    horizon_years = plan_to_age - 60 + 1
    common = dict(
        # you own $900k of the $1.5M traditional total, spouse the
        # remaining $600k -- an illustrative per-owner split
        # (011-per-owner-accounts); this reference scenario's own
        # documented $1.5M/$400k/$600k totals (accounts, above) are
        # unchanged.
        household=household, accounts=accounts,
        traditional_ownership_shares={"you": 900_000 / 1_500_000, "spouse": 600_000 / 1_500_000},
        annual_spending_need=110_000,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=plan_to_age,
    )

    print("=" * 72)
    print("Retirement Planning Tool -- reference-scenario example")
    print("=" * 72)

    # Question 1: Longevity -- what's my success rate?
    paths = generate_return_paths(
        market_assumptions=market, path_count=5_000, horizon_years=horizon_years, start_plan_year=1, seed=42
    )
    base_strategy = StrategyConfiguration(
        label="fill_to_22_pct_bracket", withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=206_700,
        conversion_window=(2028, 2034), claiming_ages={"you": 67, "spouse": 67},
    )
    run = run_simulation(**common, state="FL", strategy=base_strategy, return_paths=paths, candidate_label="base_case")
    print(f"\n[Q1 Longevity] 5,000-path Monte Carlo, FL, base strategy, plan to age {plan_to_age}:")
    print(f"  Success rate: {run.success_rate:.1%}")
    median_balance_final_year = run.percentile_bands[-1].percentiles[0.50]
    print(f"  Median ending balance (real $): ${median_balance_final_year:,.0f}")

    # Question 2: Tax optimization -- which Roth conversion strategy wins?
    candidates = [
        StrategyConfiguration(
            label="no_conversion", withdrawal_strategy="rmd_taxable_traditional_roth",
            conversion_strategy=None, conversion_bracket_ceiling_or_amount=None,
            conversion_window=None, claiming_ages={"you": 67, "spouse": 67},
        ),
        StrategyConfiguration(
            label="fill_to_10_pct_bracket", withdrawal_strategy="rmd_taxable_traditional_roth",
            conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=94_300,
            conversion_window=(2028, 2034), claiming_ages={"you": 67, "spouse": 67},
        ),
        StrategyConfiguration(
            label="fill_to_22_pct_bracket", withdrawal_strategy="rmd_taxable_traditional_roth",
            conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=206_700,
            conversion_window=(2028, 2034), claiming_ages={"you": 67, "spouse": 67},
        ),
    ]
    conversion_comparison = compare_roth_conversion_strategies(
        **common, state="FL", withdrawal_strategy="rmd_taxable_traditional_roth",
        claiming_ages={"you": 67, "spouse": 67}, return_paths=paths, candidates=candidates,
    )
    print("\n[Q2 Tax optimization] Roth conversion strategy comparison (FL, paired draws):")
    for candidate_run in conversion_comparison.runs:
        print(f"  {candidate_run.candidate_label:24s} success_rate={candidate_run.success_rate:.1%}")

    # Question 3: Location comparison -- how much does state matter?
    # SC, DE, FL are the states with real bracket-level tax modules today
    # (see docs/remaining_scope.md §4 item 1 -- GA/NC/TN/MS/PA/NH are
    # still backlog). A single-year horizon is used here because DE's
    # bracket table currently only documents tax year 2026.
    single_year = {**common, "plan_to_age": 60}
    state_paths = generate_return_paths(
        market_assumptions=market, path_count=5_000, horizon_years=1, start_plan_year=1, seed=42
    )
    state_comparison = compare_states(
        **single_year, states=["SC", "DE", "FL"], strategy=base_strategy, return_paths=state_paths,
    )
    print("\n[Q3 Location comparison] State comparison (2026 only -- DE's module only covers that year today):")
    for state_run in state_comparison.runs:
        print(f"  {state_run.candidate_label:4s} success_rate={state_run.success_rate:.1%}")

    print(
        f"\nVerification flags carried through this run: {len(run.figures_used)} sourced figures "
        f"({sum(1 for f in run.figures_used if not f.verified)} still unverified placeholders)"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
