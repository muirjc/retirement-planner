# Quickstart: Scenario Configuration & Validation

Validates the feature end-to-end: author a scenario as YAML, save it, list saved scenarios, reload one, and see validation flags — all without touching any source code, per SC-001/SC-004.

## Prerequisites

- Python 3.11+
- Dependencies installed (`pyyaml`, `pytest`) — see [plan.md](./plan.md) Technical Context; exact install command depends on the packaging setup chosen during implementation (`pip install -e .` once a `pyproject.toml` exists).
- Working directory is the repository root, so `config/scenarios/` resolves correctly.

## 1. Author a scenario

Create `config/scenarios/base_case.yaml`:

```yaml
name: base_case
household:
  filing_status: married_filing_jointly
  members:
    - person_name: you
      current_age: 60
      ss_claim_age: 67
      ss_annual_benefit: 32000
    - person_name: spouse
      current_age: 58
      ss_claim_age: 67
      ss_annual_benefit: 24000
accounts:
  - account_type: traditional
    balance: 1500000
  - account_type: roth
    balance: 400000
  - account_type: taxable
    balance: 200000
spending:
  annual_need_real: 110000
state: GA
market_assumptions:
  equity_allocation: 0.60
  equity_return_mean_real: 0.065
  equity_return_std_real: 0.17
  bond_allocation: 0.40
  bond_return_mean_real: 0.015
  bond_return_std_real: 0.06
  correlation: -0.10
simulation_settings:
  n_paths: 5000
  seed: 42
  plan_to_age: 95
```

This is a direct instance of the entities in [data-model.md](./data-model.md), matching the source document's §6 sketch.

## 2. Load and validate it (User Story 1 + 3)

```python
from retirement_planner.scenario import load_scenario

scenario = load_scenario("base_case")
assert scenario.household.members[0].person_name == "you"
assert scenario.is_usable  # no blocking flags
print(scenario.validation_flags)
# [ValidationFlag(field='spending.annual_need_real', ..., severity='warning')]
```

**Expected outcome**: the scenario loads with every authored field present and correctly typed
(Acceptance Scenario 1.1). It also carries one `warning`-severity flag: over a 35-year horizon
(`plan_to_age` 95 − age 60), $110,000/year of spending totals $3,850,000, which exceeds this
household's $2,100,000 in starting accounts — the spending-vs-assets check (FR-009) does not
offset for Social Security income by design (see data-model.md), so it correctly flags this as
worth a second look even though the household's real Social Security benefits would likely cover
the gap. `is_usable` stays `True` because a `warning` never blocks a scenario (FR-014) — this
is exactly what that severity distinction is for; to see a scenario with *zero* flags, see the
`clean_case` example in step 4.

## 3. Save a second named scenario (User Story 2)

```python
from dataclasses import replace
from retirement_planner.scenario import save_scenario, list_scenarios, load_scenario

high_spending = replace(
    scenario,
    name="high_spending",
    spending=replace(scenario.spending, annual_need_real=160000),
)
save_scenario(high_spending)

assert sorted(list_scenarios()) == ["base_case", "high_spending"]

# base_case is untouched by the high_spending save:
reloaded_base = load_scenario("base_case")
assert reloaded_base.spending.annual_need_real == 110000
```

**Expected outcome**: both scenarios are independently listed and loadable (Acceptance Scenario 2.1–2.3); editing/saving `high_spending` never altered `base_case` (FR-005, SC-003).

## 4. Trigger validation flags (User Story 3)

Create `config/scenarios/broken.yaml` with an out-of-range claiming age and a negative balance:

```yaml
name: broken
household:
  filing_status: single
  members:
    - person_name: you
      current_age: 60
      ss_claim_age: 75          # out of 62-70 range
      ss_annual_benefit: 32000
accounts:
  - account_type: traditional
    balance: -1000              # negative balance
spending:
  annual_need_real: 110000
state: GA
market_assumptions: { equity_allocation: 0.6, equity_return_mean_real: 0.065,
  equity_return_std_real: 0.17, bond_allocation: 0.4, bond_return_mean_real: 0.015,
  bond_return_std_real: 0.06, correlation: -0.10 }
simulation_settings: { n_paths: 5000, seed: 42, plan_to_age: 95 }
```

```python
broken = load_scenario("broken")
assert not broken.is_usable
by_field = {f.field: f.severity for f in broken.validation_flags}
assert by_field["household.members[0].ss_claim_age"] == "blocking"
assert by_field["accounts[traditional].balance"] == "blocking"
```

**Expected outcome**: both impossible-value problems are reported together (FR-006), each naming
its field and reason (FR-011), each `blocking` (FR-007, FR-008) — which alone is enough to make
`is_usable` `False`. (This `broken` example's spending/horizon numbers also happen to trip the
same plausibility `warning` described in step 2 — that's expected and doesn't change the outcome,
since `is_usable` only cares about `blocking` flags.)

To see a scenario with *no* flags at all — the literal Acceptance Scenario 3.4 case — shorten the
horizon so the plausibility check can't fire, e.g. `plan_to_age: 60` with `current_age: 60`:

```python
from retirement_planner.scenario import parse_scenario, save_scenario

clean_case = parse_scenario(  # same shape as broken.yaml, but valid values and a 0-year horizon
    """
    name: clean_case
    household:
      filing_status: single
      members: [{person_name: you, current_age: 60, ss_claim_age: 67, ss_annual_benefit: 32000}]
    accounts: [{account_type: traditional, balance: 500000}]
    spending: {annual_need_real: 50000}
    state: GA
    market_assumptions: {equity_allocation: 0.6, equity_return_mean_real: 0.065,
      equity_return_std_real: 0.17, bond_allocation: 0.4, bond_return_mean_real: 0.015,
      bond_return_std_real: 0.06, correlation: -0.10}
    simulation_settings: {n_paths: 5000, seed: 42, plan_to_age: 60}
    """
)
save_scenario(clean_case)
reloaded = load_scenario("clean_case")
assert reloaded.validation_flags == []
assert reloaded.is_usable is True
```

## 5. Malformed file vs. bad values (Edge Case)

```python
from retirement_planner.scenario import ScenarioParseError

# config/scenarios/unparseable.yaml contains invalid YAML syntax
try:
    load_scenario("unparseable")
    assert False, "expected ScenarioParseError"
except ScenarioParseError as e:
    print(e)  # distinct from a ValidationFlag — the file couldn't be read at all
```

**Expected outcome**: a parse failure raises `ScenarioParseError`, distinct from a scenario that parses but carries blocking `ValidationFlag`s (FR-012).

## Running the automated version

Once implemented, the equivalent assertions above are `tests/integration/test_scenario_lifecycle.py`:

```bash
pytest tests/integration/test_scenario_lifecycle.py -v
```

All steps passing is the acceptance bar for this feature — see [contracts/scenario-api.md](./contracts/scenario-api.md) for the exact function signatures exercised above.
