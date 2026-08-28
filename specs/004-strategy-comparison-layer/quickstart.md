# Quickstart: Strategy Comparison Layer

Validates the feature end-to-end: run one full-horizon projection, then compare Roth conversion strategies, withdrawal sequencing orders, and Social Security claiming ages against each other — all under one shared deterministic return assumption, all offline — per SC-001–SC-006.

> **All dollar figures, ages, rates, and thresholds below are illustrative placeholders**, chosen to demonstrate the API shape and comparison mechanics clearly — they are **not** asserted as accurate to any specific real tax year, exactly as `002` and `003`'s quickstarts note for their own placeholder figures. This feature introduces no new `SourcedFigure`s of its own (research.md §1) — every verification flag it surfaces (`figures_used`) originates from `002` or `003`.

## Prerequisites

- Python 3.11+, same environment as `001`–`003` (no new dependencies).
- No config files, no network access — this feature takes all its inputs as function arguments, same posture as `002`/`003`.

## 1. Run one full-horizon projection (User Story 1)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.comparison import (
    StrategyConfiguration, derive_deterministic_return, run_plan_projection,
)
from retirement_planner.scenario import MarketAssumptions  # illustrative import path

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
return_assumption = derive_deterministic_return(market)
# 0.60 * 0.065 + 0.40 * 0.015 = 0.045 (research.md §1)
assert round(return_assumption.annual_real_return, 3) == 0.045

strategy = StrategyConfiguration(
    label="fill_to_22_pct_bracket",
    withdrawal_strategy="rmd_taxable_traditional_roth",  # 003's shipped default
    conversion_strategy="fill_to_bracket",
    conversion_bracket_ceiling_or_amount=206_700,          # illustrative MFJ 22% ceiling
    conversion_window=(2028, 2034),
    claiming_ages={"you": 67, "spouse": 67},               # matches the scenario's configured ages
)

projection = run_plan_projection(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_assumption=return_assumption,
)

assert len(projection.years) == 95 - 60 + 1        # from age 60 through age 95 (US1.1)
assert projection.years[0].starting_balances == accounts
assert projection.years[1].starting_balances == projection.years[0].ending_balances  # US1.2
assert isinstance(projection.outcome.ending_balance, float)

# Same scenario, same strategy, same return assumption -> identical results (US1.4).
repeat = run_plan_projection(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_assumption=return_assumption,
)
assert repeat.outcome == projection.outcome
```

**Expected outcome**: one `PlanProjection` entry per plan year from the first retirement year through age 95 (US1.1), each year's ending balances feeding the next year's starting balances (US1.2), and identical inputs producing identical outputs on repeat (US1.4).

## 2. Compare Roth conversion strategies (User Story 2)

```python
from retirement_planner.comparison import compare_roth_conversion_strategies

candidates = [
    StrategyConfiguration(label="fill_to_10_pct_bracket", withdrawal_strategy="rmd_taxable_traditional_roth",
                           conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=94_300,
                           conversion_window=(2028, 2034), claiming_ages={"you": 67, "spouse": 67}),
    StrategyConfiguration(label="fill_to_22_pct_bracket", withdrawal_strategy="rmd_taxable_traditional_roth",
                           conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=206_700,
                           conversion_window=(2028, 2034), claiming_ages={"you": 67, "spouse": 67}),
    StrategyConfiguration(label="fixed_50k", withdrawal_strategy="rmd_taxable_traditional_roth",
                           conversion_strategy="fixed_amount", conversion_bracket_ceiling_or_amount=50_000,
                           conversion_window=(2028, 2034), claiming_ages={"you": 67, "spouse": 67}),
    StrategyConfiguration(label="no_conversion", withdrawal_strategy="rmd_taxable_traditional_roth",
                           conversion_strategy=None, conversion_bracket_ceiling_or_amount=None,
                           conversion_window=None, claiming_ages={"you": 67, "spouse": 67}),
]

comparison = compare_roth_conversion_strategies(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    withdrawal_strategy="rmd_taxable_traditional_roth", claiming_ages={"you": 67, "spouse": 67},
    return_assumption=return_assumption, candidates=candidates,
)

assert comparison.dimension == "roth_conversion_strategy"
assert len(comparison.projections) == 4                                   # US2.1
assert all(p.return_assumption == return_assumption for p in comparison.projections)  # US2.1, SC-005

no_conv = next(p for p in comparison.projections if p.strategy.label == "no_conversion")
fill_22 = next(p for p in comparison.projections if p.strategy.label == "fill_to_22_pct_bracket")
# Converting earlier moves income (and tax) earlier, shrinking the traditional
# balance faster and shifting where lifetime tax falls (US2.2) -- the exact
# sign of the ending-balance difference depends on the illustrative rates
# above, but the two outcomes are never identical unless the strategies'
# actual rules imply no difference (US2.3).
assert no_conv.outcome.cumulative_tax_paid != fill_22.outcome.cumulative_tax_paid
```

**Expected outcome**: one outcome per Roth conversion strategy, all computed under the identical `return_assumption` (US2.1), with outcomes differing only where the strategies' rules actually diverge (US2.2–US2.3), assembled into a single structured `ComparisonResult` (US2.4).

## 3. Compare withdrawal sequencing orders (User Story 3)

```python
from retirement_planner.comparison import compare_withdrawal_sequencing_strategies

order_candidates = [
    StrategyConfiguration(label="taxable_first", withdrawal_strategy="rmd_taxable_traditional_roth",
                           conversion_strategy=None, conversion_bracket_ceiling_or_amount=None,
                           conversion_window=None, claiming_ages={"you": 67, "spouse": 67}),
    StrategyConfiguration(label="traditional_first", withdrawal_strategy="rmd_traditional_taxable_roth",
                           conversion_strategy=None, conversion_bracket_ceiling_or_amount=None,
                           conversion_window=None, claiming_ages={"you": 67, "spouse": 67}),
]

order_comparison = compare_withdrawal_sequencing_strategies(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={"you": 67, "spouse": 67}, return_assumption=return_assumption,
    candidates=order_candidates,
)

assert order_comparison.dimension == "withdrawal_sequencing"
assert len(order_comparison.projections) == 2                              # US3.1
```

**Expected outcome**: one outcome per withdrawal order, computed under identical non-sequencing inputs (US3.1), diverging only from which account type is drawn down first (US3.2).

## 4. Compare Social Security claiming ages (User Story 4)

```python
import itertools
from retirement_planner.comparison import compare_claiming_age_grid

grid = [
    {"you": you_age, "spouse": spouse_age}
    for you_age, spouse_age in itertools.product(range(62, 71), range(62, 71))
]

age_comparison = compare_claiming_age_grid(
    household=household, accounts=accounts, annual_spending_need=110_000, state="GA",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    withdrawal_strategy="rmd_taxable_traditional_roth", conversion_strategy=None,
    conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    return_assumption=return_assumption, claiming_age_grid=grid,
)

assert age_comparison.dimension == "claiming_age_grid"
assert len(age_comparison.projections) == 9 * 9                            # US4.1

matching_original = next(
    p for p in age_comparison.projections
    if p.strategy.claiming_ages == {"you": 67, "spouse": 67}
)
assert matching_original.outcome == projection.outcome                     # US4.3, once conversion/order match
```

**Expected outcome**: one outcome per claiming-age pair across the full 62-70 grid for each spouse (US4.1), with the grid cell matching the scenario's originally configured ages reproducing Section 1's single-projection result exactly (US4.3).

## Running the automated version

Once implemented, the equivalent assertions above are `tests/integration/test_comparison_lifecycle.py`:

```bash
pytest tests/integration/test_comparison_lifecycle.py -v
```

All steps passing is the acceptance bar for this feature — see [contracts/comparison-api.md](./contracts/comparison-api.md) for the exact function signatures exercised above.
