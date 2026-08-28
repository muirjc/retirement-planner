# Quickstart: Reporting & Aggregation

Validates the feature end-to-end: summarize one simulation run, summarize a comparison (both the Monte Carlo and deterministic kinds), export both to CSV, and confirm unverified figures are visible throughout — all offline — per SC-001–SC-005.

> **All dollar figures, ages, and rates below are illustrative placeholders**, exactly as `004`/`005`'s quickstarts note for their own placeholder figures. This feature introduces no new figures of its own (research.md's Constitution Check) — every unverified-figure name it surfaces originates from `002`/`003`/`005`.

## Prerequisites

- Python 3.11+, same environment as `001`–`005` (no new dependencies).
- No config files, no network access — this feature takes already-computed result objects as function arguments, same posture as `004`/`005`.

## 1. Summarize one simulation run (User Story 1)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions
from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.simulation import generate_return_paths, run_simulation
from retirement_planner.reporting import summarize_run

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
strategy = StrategyConfiguration(
    label="fill_to_22_pct_bracket", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=206_700,
    conversion_window=(2028, 2034), claiming_ages={"you": 67, "spouse": 67},
)
return_paths = generate_return_paths(
    market_assumptions=market, path_count=5_000, horizon_years=36, start_plan_year=1, seed=42,
)
run = run_simulation(
    household=household, accounts=accounts, annual_spending_need=110_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_paths=return_paths, candidate_label="base_case",
)

summary = summarize_run(run, household=household, reference_tax_year=2026)

assert summary.candidate_label is None                                  # US1, not part of a comparison
assert summary.success_rate == run.success_rate                          # US1.1
assert summary.percentile_bands == run.percentile_bands                  # US1.1
assert isinstance(summary.median_lifetime_tax_paid, float)               # US1.4 -- computed across all paths
if run.success_rate < 1.0:
    assert summary.median_depletion_age is not None                     # US1.2
else:
    assert summary.median_depletion_age is None                        # US1.3 -- not applicable, not zero
assert isinstance(summary.unverified_figure_names, list)                 # US4.1/US4.2 -- always present

# Same run summarized twice -> identical results (US1.5).
assert summarize_run(run, household=household, reference_tax_year=2026) == summary
```

**Expected outcome**: a complete `SummaryStatistics` for one run, with `success_rate`/`percentile_bands` matching the run's own fields (US1.1), `median_depletion_age` correctly present or absent depending on whether any path actually depleted (US1.2–US1.3), `median_lifetime_tax_paid` computed across every path regardless of outcome (US1.4), and identical results on repeat (US1.5).

## 2. Compare candidates with the same summary shape (User Story 2)

```python
from retirement_planner.simulation import compare_states
from retirement_planner.reporting import summarize_simulation_comparison

comparison = compare_states(
    household=household, accounts=accounts, annual_spending_need=110_000,
    states=["SC", "DE", "FL"], reference_tax_year=2026, start_plan_year=1, start_tax_year=2026,
    plan_to_age=60,  # single-plan-year horizon -- keeps every state within its documented tax years
    strategy=strategy, return_paths=generate_return_paths(
        market_assumptions=market, path_count=5_000, horizon_years=1, start_plan_year=1, seed=42,
    ),
)

summaries = summarize_simulation_comparison(comparison, household=household, reference_tax_year=2026)

assert len(summaries) == len(comparison.runs) == 3                       # US2.1
for summary, run in zip(summaries, comparison.runs):
    assert summary.candidate_label == run.candidate_label                # US2.1, same order
    assert summary == summarize_run(run, household=household, reference_tax_year=2026)  # US2.1
```

```python
from retirement_planner.comparison import compare_roth_conversion_strategies, derive_deterministic_return
from retirement_planner.reporting import summarize_deterministic_comparison

deterministic = compare_roth_conversion_strategies(
    household=household, accounts=accounts, annual_spending_need=110_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=70,
    withdrawal_strategy="rmd_taxable_traditional_roth", claiming_ages={"you": 67, "spouse": 67},
    return_assumption=derive_deterministic_return(market),
    candidates=[strategy],
)
deterministic_summaries = summarize_deterministic_comparison(deterministic, household=household, reference_tax_year=2026)

assert len(deterministic_summaries) == 1
assert deterministic_summaries[0].success_rate is None                   # US2.2 -- not applicable
assert deterministic_summaries[0].percentile_bands is None               # US2.2 -- not applicable
assert isinstance(deterministic_summaries[0].ending_balance, float)      # US2.2 -- genuinely available
```

**Expected outcome**: a comparison's summaries match calling `summarize_run()` on each candidate directly, in the comparison's own order (US2.1), and a deterministic (`004`) comparison's summaries correctly mark Monte-Carlo-only fields as not applicable while still reporting the fields a deterministic candidate genuinely has (US2.2).

## 3. Export a report to CSV (User Story 3)

```python
from retirement_planner.reporting import run_to_csv_text, simulation_comparison_to_csv_text

run_csv = run_to_csv_text(run)
assert run_csv.splitlines()[0].startswith("plan_year")                  # header row
assert len(run_csv.splitlines()) == 1 + len(run.percentile_bands)        # US3.1 -- one row per plan year

comparison_csv = simulation_comparison_to_csv_text(comparison, household=household, reference_tax_year=2026)
assert len(comparison_csv.splitlines()) == 1 + len(comparison.runs)      # US3.2 -- one row per candidate
assert all(state in comparison_csv for state in ("SC", "DE", "FL"))      # US3.2 -- clearly labeled
```

**Expected outcome**: spreadsheet-ready CSV text for both a single run (one row per plan year) and a comparison (one row per candidate, clearly labeled), with every value traceable back to the underlying result (US3.1–US3.2).

## 4. Confirm unverified figures stay visible (User Story 4)

```python
# 005's historical-bootstrap and survival-adjusted paths always carry
# unverified placeholder figures (HISTORICAL_RETURNS/SURVIVAL_TABLE,
# per 005's research.md §4-5) -- a reliable fixture for this check.
from retirement_planner.simulation import generate_historical_bootstrap_paths

bootstrap_paths = generate_historical_bootstrap_paths(
    market_assumptions=market, path_count=1_000, horizon_years=36, start_plan_year=1, seed=42, block_length=10,
)
bootstrap_run = run_simulation(
    household=household, accounts=accounts, annual_spending_need=110_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_paths=bootstrap_paths, candidate_label="historical_bootstrap",
)
bootstrap_summary = summarize_run(bootstrap_run, household=household, reference_tax_year=2026)

assert "historical_annual_real_returns" in bootstrap_summary.unverified_figure_names  # US4.1
assert len(bootstrap_summary.unverified_figure_names) == len(set(bootstrap_summary.unverified_figure_names))  # dedup

bootstrap_csv = run_to_csv_text(bootstrap_run)
assert "has_unverified_figure" in bootstrap_csv.splitlines()[0]          # US3.3 -- surfaced in export too
```

**Expected outcome**: a run known to depend on an unverified figure (`005`'s synthetic historical-return series) surfaces that figure's name explicitly in both the summary (US4.1) and the CSV export (US3.3) — never merely by its absence from a "verified" list.

## Running the automated version

Once implemented, the equivalent assertions above are `tests/integration/test_reporting_lifecycle.py`:

```bash
pytest tests/integration/test_reporting_lifecycle.py -v
```

All steps passing is the acceptance bar for this feature — see [contracts/reporting-api.md](./contracts/reporting-api.md) for the exact function signatures exercised above.
