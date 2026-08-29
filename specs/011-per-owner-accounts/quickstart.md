# Quickstart: Per-Owner Account Attribution

Validates the feature end-to-end: a married household where each spouse owns a separate traditional account of a different size, ages far enough apart that only one spouse has reached the RMD-required starting age in the first modeled plan year — confirming each spouse's RMD is computed from their own balance and own age, not the household's combined total attributed to one deemed owner (SC-001). Also validates the scenario-layer contract directly: single-filer auto-fill (SC-004) and the blocking-flag behavior for a scenario missing owner data (SC-002).

## Prerequisites

- Python 3.11+, same environment as `001`–`010` (no new dependency).
- No config files, no network access — same offline posture as every prior engine feature.

## 1. Per-member RMD accuracy (User Story 1)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection

household = Household(
    filing_status="married_filing_jointly",
    members=[
        HouseholdMember(person_name="you", current_age=74, ss_claim_age=67, ss_annual_benefit=32_000),
        HouseholdMember(person_name="spouse", current_age=60, ss_claim_age=67, ss_annual_benefit=24_000),
    ],
)
# "you" owns $900k of the $1.2M household traditional total; "spouse" owns $300k.
accounts = AccountBalances(traditional=1_200_000, roth=400_000, taxable=300_000)
traditional_ownership_shares = {"you": 900_000 / 1_200_000, "spouse": 300_000 / 1_200_000}

strategy = StrategyConfiguration(
    label="base_case", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={"you": 67, "spouse": 67},
)

projection = run_plan_projection(
    household=household, accounts=accounts, traditional_ownership_shares=traditional_ownership_shares,
    annual_spending_need=90_000, state="FL", reference_tax_year=2026, start_plan_year=1, start_tax_year=2026,
    plan_to_age=95, strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
)

first_year = projection.years[0]
# "you" (74) is past the RMD-required starting age; "spouse" (60) is not --
# before this feature, the entire $1.2M was attributed to "you" (the older
# member) regardless of the real $900k/$300k split. Confirm the RMD-driven
# traditional draw reflects only "you"'s own $900k share, not the full $1.2M.
print(first_year.mechanics.withdrawal_plan.rmd_drawn)  # sized to $900k @ "you"'s divisor, not $1.2M
```

Re-running a decade later (once `current_age`s translate past 70 for both members) shows both members' RMDs contributing to `rmd_drawn`, each still sized to their own fixed share of that year's pooled traditional balance (data-model.md § Derived) — confirming SC-001 holds across the full horizon, not just the first crossing year.

## 2. Single-filer scenarios are unaffected (User Story 3, SC-004)

```python
from retirement_planner.scenario import parse_scenario, validate

single_filer_yaml = """
name: solo
household:
  filing_status: single
  members:
    - person_name: you
      current_age: 74
      ss_claim_age: 67
      ss_annual_benefit: 32000
accounts:
  - account_type: traditional
    balance: 900000
  # no `owner:` key -- predates this feature
spending:
  annual_need_real: 60000
state: FL
market_assumptions:
  equity_allocation: 0.6
  equity_return_mean_real: 0.05
  equity_return_std_real: 0.15
  bond_allocation: 0.4
  bond_return_mean_real: 0.02
  bond_return_std_real: 0.05
  correlation: 0.0
simulation_settings:
  n_paths: 1
  seed: 1
  plan_to_age: 95
"""

scenario = parse_scenario(single_filer_yaml, name="solo")
assert scenario.accounts[0].owner == "you"  # auto-filled, no edit needed (research.md §3)
flags = validate(scenario)
assert not any(f.field.startswith("accounts[") and "owner" in f.field for f in flags)
```

## 3. A married scenario missing owner data surfaces a specific, actionable flag (User Story 3, SC-002)

```python
married_yaml_missing_owner = """
name: couple
household:
  filing_status: married_filing_jointly
  members:
    - {person_name: you, current_age: 74, ss_claim_age: 67, ss_annual_benefit: 32000}
    - {person_name: spouse, current_age: 60, ss_claim_age: 67, ss_annual_benefit: 24000}
accounts:
  - account_type: traditional
    balance: 900000
  # no `owner:` key -- ambiguous with two household members
spending:
  annual_need_real: 90000
state: FL
market_assumptions: {equity_allocation: 0.6, equity_return_mean_real: 0.05, equity_return_std_real: 0.15,
                      bond_allocation: 0.4, bond_return_mean_real: 0.02, bond_return_std_real: 0.05, correlation: 0.0}
simulation_settings: {n_paths: 1, seed: 1, plan_to_age: 95}
"""

scenario = parse_scenario(married_yaml_missing_owner, name="couple")
assert scenario.accounts[0].owner is None
flags = validate(scenario)
owner_flags = [f for f in flags if f.field == "accounts[0].owner"]
assert len(owner_flags) == 1 and owner_flags[0].severity == "blocking"

# validate() doesn't mutate the scenario -- Scenario.is_usable reads
# validation_flags, which the caller assigns explicitly (same discipline
# load_scenario() already applies internally for every existing scenario).
scenario.validation_flags = flags
assert scenario.is_usable is False
```

## Running the full stack (API + UI) to see it end-to-end

Same startup as the README's "Running the full stack" section — no new environment variable or config. Open the Streamlit UI's Scenarios page, add a second household member, add a traditional account, and confirm the owner selector offers exactly that household's current member names (`ui-pages.md`, this feature).
