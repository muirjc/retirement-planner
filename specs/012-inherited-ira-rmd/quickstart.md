# Quickstart: Inherited IRA (Already-in-RMD-Status) Modeling

Validates the feature end-to-end: a beneficiary who inherited a traditional IRA from a parent who had already begun their own RMDs before dying — confirming the inherited account's own annual distribution is computed and included in the plan (SC-001), the account is fully depleted by its 10-year deadline (SC-002), an unsupported case (pre-RBD death, EDB beneficiary, non-traditional account) is blocked with a specific message rather than silently computed (SC-003), two inherited accounts from different decedents don't interfere with each other (SC-004), and a Monte Carlo simulation request against such a scenario is explicitly rejected (FR-013) rather than silently dropping the inherited account.

Every dollar figure below depends on the actual `SINGLE_LIFE_EXPECTANCY_TABLE` divisor values an implementation populates (research.md §7, §9.8 — partial/illustrative coverage, `verified=False`) — this guide checks the *relationships* FR-001–FR-013 require, not specific hardcoded divisors, since those numbers aren't fixed by this design phase.

## Prerequisites

- Python 3.11+, same environment as `001`–`011` (no new dependency).
- No config files, no network access — same offline posture as every prior engine feature.

## 1. Annual distribution is computed and included in the plan (User Story 1, SC-001)

```python
from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection

household = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=28_000)],
)
# "you" inherited a traditional IRA from a parent who died in 2023 at age 80,
# already taking their own RMDs -- the supported case (research.md §2).
inherited_accounts = [
    InheritedAccountBalance(
        account_id="traditional-1",
        balance=250_000,
        death_year=2023,
        decedent_age_at_death=80,
        depletion_deadline_year=2033,  # death_year + 10
    )
]

strategy = StrategyConfiguration(
    label="base_case", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={"you": 67},
)

projection = run_plan_projection(
    household=household,
    accounts=AccountBalances(traditional=0, roth=0, taxable=100_000),
    traditional_ownership_shares={"you": 0.0},  # "you" owns no ordinary traditional account
    inherited_accounts=inherited_accounts,
    annual_spending_need=60_000, state="FL", reference_tax_year=2026, start_plan_year=1, start_tax_year=2026,
    plan_to_age=95, strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
)

first_year = projection.years[0]
# Before this feature, an inherited account contributed nothing at all --
# rmd_amount only ever came from compute_rmd() against "you"'s own
# traditional_ownership_shares-derived balance (here, $0). Confirm the
# inherited account's own distribution shows up in this year's mechanics.
assert first_year.mechanics.withdrawal_plan.inherited_distribution_drawn > 0
# The inherited balance itself never appears in AccountBalances -- confirm
# the pooled traditional balance the projection tracks is still $0,
# unaffected by the inherited account entirely (research.md §5).
assert first_year.starting_balances.traditional == 0
```

## 2. Full depletion by the 10-year deadline (User Story 2, SC-002)

```python
# Re-running the same setup across the full horizon: by tax_year 2033
# (death_year + 10), the inherited account must be fully depleted,
# regardless of what the divisor-computed annual amount alone would
# have left behind.
deadline_year_projection = [year for year in projection.years if year.tax_year == 2033][0]
# The account's own remaining balance after the deadline year's forced
# full distribution is 0 -- confirmed indirectly: every plan year after
# 2033 contributes no further inherited_distribution_drawn at all.
later_years = [year for year in projection.years if year.tax_year > 2033]
assert all(year.mechanics.withdrawal_plan.inherited_distribution_drawn == 0 for year in later_years)
```

## 3. Unsupported cases are blocked, not silently computed (User Story 3, SC-003)

```python
from retirement_planner.scenario import parse_scenario, validate

def _scenario_yaml(inherited_block: str) -> str:
    return f"""
name: inherited_case
household:
  filing_status: single
  members:
    - person_name: you
      current_age: 55
      ss_claim_age: 67
      ss_annual_benefit: 28000
accounts:
  - account_type: traditional
    balance: 250000
    owner: you
    inherited:
{inherited_block}
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

# Case A: owner died before beginning their own RMDs (pre-RBD, FR-006).
pre_rbd_yaml = _scenario_yaml("""      death_year: 2023
      decedent_age_at_death: 68
      decedent_was_taking_rmds: false
      beneficiary_relationship: other_individual
      beneficiary_classification: non_eligible_designated_beneficiary""")
scenario = parse_scenario(pre_rbd_yaml, name="inherited_case")
flags = validate(scenario)
assert any(f.field == "accounts[0].inherited" and f.severity == "blocking" for f in flags)

# Case B: beneficiary is an eligible designated beneficiary (FR-007).
edb_yaml = _scenario_yaml("""      death_year: 2023
      decedent_age_at_death: 80
      decedent_was_taking_rmds: true
      beneficiary_relationship: spouse
      beneficiary_classification: eligible_designated_beneficiary_spouse""")
scenario = parse_scenario(edb_yaml, name="inherited_case")
flags = validate(scenario)
assert any(f.field == "accounts[0].inherited" and f.severity == "blocking" for f in flags)

# Case C: inherited account is Roth, not traditional (FR-012).
roth_yaml = _scenario_yaml("""      death_year: 2023
      decedent_age_at_death: 80
      decedent_was_taking_rmds: true
      beneficiary_relationship: other_individual
      beneficiary_classification: non_eligible_designated_beneficiary""").replace(
    "account_type: traditional", "account_type: roth"
)
scenario = parse_scenario(roth_yaml, name="inherited_case")
flags = validate(scenario)
assert any(f.field == "accounts[0].inherited" and f.severity == "blocking" for f in flags)
```

## 4. Two inherited accounts from different decedents don't interfere (SC-004)

```python
inherited_accounts = [
    InheritedAccountBalance(
        account_id="traditional-1", balance=250_000,
        death_year=2023, decedent_age_at_death=80, depletion_deadline_year=2033,
    ),
    InheritedAccountBalance(
        account_id="traditional-2", balance=90_000,
        death_year=2020, decedent_age_at_death=75, depletion_deadline_year=2030,
    ),
]
# Changing one account's facts (e.g. its decedent's age at death) must
# never change the other's computed distribution -- each is looked up
# and mutated independently by account_id (research.md §8, data-model.md).
```

## 5. A Monte Carlo simulation request is rejected, not silently run (FR-013)

```python
from fastapi.testclient import TestClient
# (client fixture wired the same way every other services/bff test already is)

response = client.post("/simulations", json={
    "scenario_name": "inherited_case",  # a saved scenario with an inherited account
    "reference_tax_year": 2026, "start_plan_year": 1, "start_tax_year": 2026,
})
assert response.status_code == 422
assert response.json()["error"] == "inherited_accounts_unsupported_for_simulation"

# The deterministic-comparison / single-projection path for the same
# scenario is unaffected -- POST /scenarios/{name}/validate and a
# deterministic POST /comparisons request both succeed normally.
```

## Running the full stack (API only)

Same startup as the README's "Running the full stack" section — no new environment variable or config. This feature has no Streamlit UI surface (plan.md's Structure Decision) — enter `account_id`/`inherited` fields directly in a scenario's YAML, or in `PUT /scenarios/{name}`'s request body (`AccountRequest.account_id`/`.inherited`, bff-api.md), and use `POST /scenarios/{name}/validate` to confirm a supported configuration before running a projection or deterministic comparison.
