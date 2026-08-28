# Quickstart: Simulation Engine

Validates the feature end-to-end: generate a Paired-Draw Set, run a probabilistic Monte Carlo simulation for one configuration, compare candidates across the state axis using that same shared path set, switch to historical-bootstrap return generation, apply a configurable stress scenario, and compute a survival-adjusted success rate alongside the standard one — all offline — per SC-001–SC-007.

> **All dollar figures, ages, rates, thresholds, and the illustrative historical/survival data referenced below are placeholders**, chosen to demonstrate the API shape and aggregation mechanics clearly — they are **not** asserted as accurate to any specific real tax year or verified life table, exactly as `002`–`004`'s quickstarts note for their own placeholder figures. `HISTORICAL_RETURNS` and `SURVIVAL_TABLE` (research.md §4–5) ship `verified=False` and propagate that into every run's `figures_used`.

## Prerequisites

- Python 3.11+, same environment as `001`–`004` (no new dependencies).
- No config files, no network access — this feature takes all its inputs as function arguments, same posture as `002`–`004`.

## 1. Run a probabilistic Monte Carlo simulation for one configuration (User Story 1)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions
from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.simulation import generate_return_paths, run_simulation

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

HORIZON_YEARS = 95 - 60 + 1  # deemed owner's current age (60) through plan_to_age (95), inclusive
return_paths = generate_return_paths(
    market_assumptions=market, path_count=5_000, horizon_years=HORIZON_YEARS,
    start_plan_year=1, seed=42,
)
assert len(return_paths) == 5_000

strategy = StrategyConfiguration(
    label="fill_to_22_pct_bracket", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=206_700,
    conversion_window=(2028, 2034), claiming_ages={"you": 67, "spouse": 67},
)

run = run_simulation(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_paths=return_paths, candidate_label="base_case",
)

assert len(run.path_results) == 5_000                       # one projection per path (US1.1)
assert 0.0 <= run.success_rate <= 1.0                        # US1.2
assert any(p.outcome.first_shortfall_plan_year is not None for p in run.path_results) or run.success_rate == 1.0
assert len(run.percentile_bands) == HORIZON_YEARS             # US1.1

# Same scenario, configuration, path set -> identical results (US1.3).
repeat = run_simulation(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_paths=return_paths, candidate_label="base_case",
)
assert repeat.success_rate == run.success_rate
assert repeat.percentile_bands == run.percentile_bands
```

**Expected outcome**: one `PlanProjection` per requested path (US1.1), a `success_rate` derived from the share of paths that never fell short (US1.2), and identical inputs producing identical `success_rate`/`percentile_bands` on repeat (US1.3) — regardless of whether path-level work ran in parallel (research.md §7).

## 2. Compare candidate states using the same Paired-Draw Set (User Story 2)

```python
from retirement_planner.simulation import compare_states, generate_return_paths

# SC's and DE's bracket tables currently document only 2026-2027 and 2026
# respectively (002's own illustrative-data scope) -- a single-plan-year
# comparison keeps every candidate state within its documented years.
one_year_paths = generate_return_paths(
    market_assumptions=market, path_count=5_000, horizon_years=1, start_plan_year=1, seed=42,
)

comparison = compare_states(
    household=household, accounts=accounts, annual_spending_need=110_000,
    states=["SC", "DE", "FL"],  # every state currently registered in 002's STATE_MODULES
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=60,
    strategy=strategy, return_paths=one_year_paths,
)

assert comparison.axis == "state"
assert len(comparison.runs) == 3                                          # US2.1
assert comparison.return_paths is one_year_paths                          # US2.1, structural pairing (research.md §2)

for run in comparison.runs:
    # Every candidate's path i is that same path i's return sequence (US2.3).
    # Value equality (==), not object identity (is): once path_count crosses
    # the parallel-dispatch threshold (research.md §7), a worker-process
    # round trip through pickling produces a deserialized copy, not the
    # exact same object -- the structural pairing guarantee that holds
    # regardless of dispatch is that every candidate consumes the identical
    # *values*, path-for-path (identity itself only holds under serial,
    # below-threshold dispatch -- see tests/unit/simulation/test_compare.py).
    assert run.path_results[0].return_assumption == one_year_paths[0]

fl_run = next(r for r in comparison.runs if r.candidate_label == "FL")
sc_run = next(r for r in comparison.runs if r.candidate_label == "SC")
# FL has no state income tax; SC taxes ordinary income above its bracket
# floor -- the two success rates are not required to differ (a household
# well within its assets either way could show 100% for both), but they
# must never be forced apart or together artificially (US2.2, US2.4).
```

**Expected outcome**: one `success_rate`/`percentile_bands` per state, every candidate's path `i` sharing the identical return sequence `return_paths[i]` (US2.1, US2.3), assembled into a single `SimulationComparisonResult` (US2.4) — this is the source document's §1 "Location comparison" question, delivered for the first time.

## 3. Generate returns from historical-bootstrap resampling instead of the parametric distribution (User Story 3)

```python
from retirement_planner.simulation import generate_historical_bootstrap_paths

bootstrap_paths = generate_historical_bootstrap_paths(
    market_assumptions=market, path_count=5_000, horizon_years=HORIZON_YEARS,
    start_plan_year=1, seed=42, block_length=10,
)
assert len(bootstrap_paths) == 5_000
assert all(p.generation_mode == "historical_bootstrap" for p in bootstrap_paths)
assert all(len(p.figures_used) > 0 for p in bootstrap_paths)   # HISTORICAL_RETURNS usage, unverified (US3.1)

bootstrap_run = run_simulation(
    household=household, accounts=accounts, annual_spending_need=110_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_paths=bootstrap_paths, candidate_label="historical_bootstrap",
)
assert 0.0 <= bootstrap_run.success_rate <= 1.0   # same aggregation shape as parametric mode (US3.3)

# Same seed and parameters twice -> identical resampled sequences (US3.2).
repeat_bootstrap = generate_historical_bootstrap_paths(
    market_assumptions=market, path_count=5_000, horizon_years=HORIZON_YEARS,
    start_plan_year=1, seed=42, block_length=10,
)
assert repeat_bootstrap == bootstrap_paths
```

**Expected outcome**: a path set built from resampled historical blocks rather than parametric draws (US3.1), reproducible under a fixed seed (US3.2), and consumable by the identical `run_simulation()`/`compare_*()` aggregation logic as parametric-mode paths (US3.3) — with `figures_used` carrying the unverified historical-series citation into the run (research.md §4).

## 4. Apply a configurable sequence-of-returns stress scenario (User Story 4)

```python
from retirement_planner.simulation import StressScenario, apply_stress_scenario

early_shock = StressScenario(magnitude=-0.30, duration_years=2, start_plan_year=1)
late_shock = StressScenario(magnitude=-0.30, duration_years=2, start_plan_year=20)

early_paths = apply_stress_scenario(return_paths, early_shock, horizon_last_plan_year=HORIZON_YEARS)
late_paths = apply_stress_scenario(return_paths, late_shock, horizon_last_plan_year=HORIZON_YEARS)

assert early_paths[0].annual_returns[0] == -0.30           # shock window overridden (US4.1)
assert early_paths[0].annual_returns[2] == return_paths[0].annual_returns[2]  # outside window, unchanged

early_run = run_simulation(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_paths=early_paths, candidate_label="shock_year_1",
)
late_run = run_simulation(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_paths=late_paths, candidate_label="shock_year_20",
)
# Identical shock magnitude/duration, different timing -> not required to
# produce the same success rate (US4.2) -- sequence-of-returns risk is
# exactly the point being tested.
```

**Expected outcome**: the shock window's plan years are overridden to the configured magnitude while every other year keeps its originally generated return (US4.1), and shocks placed at different points in retirement are free to produce different outcomes (US4.2) — the mechanism the source document's fixed "bad first 5 years" case generalizes into.

## 5. Compute a survival-adjusted success rate alongside the standard one (User Story 5)

```python
from retirement_planner.simulation import SURVIVAL_TABLE

survival_run = run_simulation(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_paths=return_paths, candidate_label="base_case_survival",
    survival_curves={"you": SURVIVAL_TABLE["primary"], "spouse": SURVIVAL_TABLE["spouse"]},
)

assert survival_run.success_rate == run.success_rate                        # US5.2: unaffected by the flag
assert survival_run.survival_adjusted_success_rate is not None              # US5.1
assert survival_run.survival_adjusted_success_rate >= survival_run.success_rate  # a shortfall after both
                                                                              # members are presumed deceased
                                                                              # only ever helps this metric (US5.3)
assert run.survival_adjusted_success_rate is None                           # never computed unless requested
```

**Expected outcome**: the fixed-horizon `success_rate` is identical whether or not survival-adjusted scoring is requested (US5.2), the survival-adjusted figure is `None` unless explicitly requested, and — since a shortfall occurring after both members are presumed deceased can only convert a fixed-horizon failure into a survival-adjusted success, never the reverse — `survival_adjusted_success_rate` is always at least `success_rate` (US5.1, US5.3).

## Running the automated version

Once implemented, the equivalent assertions above are `tests/integration/test_simulation_lifecycle.py`:

```bash
pytest tests/integration/test_simulation_lifecycle.py -v
```

The reference-scale performance budget (SC-003, research.md §7 — the Constitution Check's open Performance Budget gate) is validated separately:

```bash
pytest tests/integration/test_simulation_performance.py -v
```

All steps passing, including the performance benchmark, is the acceptance bar for this feature — see [contracts/simulation-api.md](./contracts/simulation-api.md) for the exact function signatures exercised above.
