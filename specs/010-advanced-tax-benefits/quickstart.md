# Quickstart: Advanced Tax & Benefits Modeling

Validates the feature end-to-end: run a full-horizon projection for a household that crosses an IRMAA tier, has investment income above the NIIT threshold, and includes a younger spouse who keeps HSA eligibility after the older spouse enrolls in Medicare — all through the same `run_plan_projection()` entry point `004`/`005` already use — per SC-001–SC-004.

> **All dollar figures, ages, and thresholds below are illustrative placeholders**, exactly as `002`–`005`'s quickstarts note for their own placeholder figures. `IrmaaTierTable`, the NIIT threshold/rate, and the HSA contribution limits all ship `verified=False` and propagate that into every run's `figures_used`, same as every other tax figure in this project.

## Prerequisites

- Python 3.11+, same environment as `001`–`009` (no new dependency).
- No config files, no network access — same offline posture as every prior engine feature.

## 1. See the IRMAA surcharge a strategy triggers (User Story 1)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection

household = Household(
    filing_status="married_filing_jointly",
    members=[
        HouseholdMember(person_name="you", current_age=66, ss_claim_age=67, ss_annual_benefit=32_000),
        HouseholdMember(person_name="spouse", current_age=64, ss_claim_age=67, ss_annual_benefit=24_000, hdhp_coverage=True),
    ],
)
accounts = AccountBalances(traditional=1_800_000, roth=400_000, taxable=300_000)
strategy = StrategyConfiguration(
    label="large_conversion", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=400_000,
    conversion_window=(2026, 2030), claiming_ages={"you": 67, "spouse": 67},
)

projection = run_plan_projection(
    household=household, accounts=accounts, annual_spending_need=110_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
)

first_year = projection.years[0]
print(first_year.irmaa.magi, first_year.irmaa.tier_crossed, first_year.irmaa.surcharge_owed)
```

**Expected outcome**: a large enough conversion pushes `first_year.irmaa.magi` into a documented tier — `tier_crossed` is not `None` and `surcharge_owed` is greater than `0.0`, distinct from `first_year.federal_tax.federal_tax_owed`/`first_year.state_tax.state_tax_owed` (Acceptance Scenario US1.2). `projection.outcome.cumulative_irmaa_paid` sums this across every plan year (SC-001).

## 2. See the NIIT surtax investment income triggers (User Story 2)

Using the same `household`/`accounts` above, but a smaller conversion that stays income-modest while the taxable account still funds a large share of spending (so taxable-account withdrawals — this feature's investment-income proxy, research.md §1 — are large relative to income):

```python
strategy_niit = StrategyConfiguration(
    label="taxable_heavy", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={"you": 67, "spouse": 67},
)
projection_niit = run_plan_projection(
    household=household, accounts=accounts, annual_spending_need=180_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
    strategy=strategy_niit, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
)
year = projection_niit.years[0]
print(year.niit.investment_income, year.niit.threshold_exceeded, year.niit.surtax_owed)
```

**Expected outcome**: when the household's MAGI exceeds the NIIT threshold, `threshold_exceeded` is `True` and `surtax_owed` reflects only the lesser of investment income and the amount over the threshold (Acceptance Scenario US2.2) — never the household's full income.

## 3. See HSA eligibility survive one spouse's Medicare enrollment (User Story 3)

Same `household` as §1 — `spouse` (age 64, `hdhp_coverage=True`) is not yet Medicare-eligible while `you` (age 66) already is:

```python
# hsa_contribution is a Scenario-level field (data-model.md), not a
# run_plan_projection() argument directly -- this quickstart calls the
# mechanics functions directly instead, per contracts/mechanics-api.md:
from retirement_planner.mechanics.hsa import compute_hsa_contribution, compute_hsa_eligibility

eligibility = compute_hsa_eligibility(
    members=[("you", 66, False), ("spouse", 64, True)],
    medicare_enrolled={"you": True, "spouse": False},
)
result = compute_hsa_contribution(eligibility, configured_annual_amount=8_000, tax_year=2026)
print([(e.person_name, e.eligible) for e in result.eligible_members], result.amount_contributed)
```

**Expected outcome**: `eligible_members` shows `you` as `eligible=False` (Medicare-enrolled) and `spouse` as `eligible=True`, independent of `you`'s status (Acceptance Scenario US3.3); `amount_contributed` reflects the self-only limit (only one member eligible), not $0 and not the family limit.

## Running the automated version

```bash
pytest tests/unit/tax/test_irmaa.py tests/unit/tax/test_niit.py tests/unit/mechanics/test_hsa.py -v
pytest tests/integration/test_advanced_tax_benefits_lifecycle.py -v
```

Both passing (plus the manual walkthrough above at least once) is the acceptance bar for this feature — see [contracts/tax-api.md](./contracts/tax-api.md), [contracts/mechanics-api.md](./contracts/mechanics-api.md), and [contracts/scenario-api.md](./contracts/scenario-api.md) for the exact shapes exercised above.
