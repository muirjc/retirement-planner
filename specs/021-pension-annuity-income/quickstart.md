# Quickstart: Pension, Annuity & Phased-Retirement Income Streams

## Prerequisites

- Repo checked out, core deps installed (`pip install -e .` from repo root, or the project's existing dev setup).
- `pytest tests/` currently passing on `main` before starting (baseline).

## 1. Add a pension to a scenario YAML

Add `income_streams` under a member in any `config/scenarios/*.yaml` file (or a test fixture):

```yaml
household:
  filing_status: single
  members:
    - person_name: "Alex"
      current_age: 60
      ss_claim_age: 67
      ss_annual_benefit: 24000
      income_streams:
        - label: "State Pension"
          stream_type: pension
          start_age: 62
          annual_amount: 18000
          inflation_adjustment: cola_adjusted
        - label: "Old 401(k)-funded annuity"
          stream_type: annuity
          start_age: 65
          end_age: 74
          annual_amount: 6000
          inflation_adjustment: fixed_nominal
```

## 2. Verify parsing/validation round-trips

```python
from retirement_planner.scenario import parse_scenario, validate

scenario = parse_scenario(open("config/scenarios/your_file.yaml").read())
assert scenario.household.members[0].income_streams[0].annual_amount == 18000
assert validate(scenario) == []  # no blocking/warning flags for a well-formed stream
```

## 3. Verify a single year's amount

```python
from retirement_planner.mechanics.income_streams import compute_income_stream_amount

stream = scenario.household.members[0].income_streams[0]  # cola_adjusted pension
result = compute_income_stream_amount(stream, member_age_this_year=70, tax_year=2036, reference_tax_year=2026)
assert result.amount == 18000  # flat, no erosion (US1 Acceptance Scenario 1)

nominal_stream = scenario.household.members[0].income_streams[1]  # fixed_nominal annuity
eroded = compute_income_stream_amount(nominal_stream, member_age_this_year=70, tax_year=2036, reference_tax_year=2026)
assert eroded.amount < 6000  # real value has eroded 10 years' worth (US1 Acceptance Scenario 2)
assert eroded.figures_used  # carries the INFLATION_RATE citation
```

## 4. Verify the full projection picks it up

```python
from retirement_planner.comparison import run_plan_projection
# ... build accounts/strategy/return_assumption as any existing comparison test does ...
projection = run_plan_projection(household=scenario.household, ...)
year = projection.years[2]  # the member's age-62 year, pension now active
assert year.member_income_stream_amounts["Alex"] > 0
assert year.federal_tax.taxable_social_security >= 0  # unaffected in shape
```

## 5. Verify a no-streams scenario is unchanged (SC-003)

Run any existing scenario fixture with no `income_streams` configured through `run_plan_projection()` before and after this feature; every `PlanYearProjection` field (besides the new `member_income_stream_amounts`, which is `{}`) must match exactly.

## 6. Run the test suites

```bash
pytest tests/                        # core: scenario, mechanics, comparison, reporting
pytest services/bff/tests/           # BFF schema pass-through
pytest apps/streamlit_ui/tests/      # UI round-trip (no data loss on save)
```

## Expected outcome

- A configured pension/annuity/earned-income stream shows up as taxable ordinary income exactly during its active age window, correctly sized (flat for `cola_adjusted`, eroding for `fixed_nominal`), in every plan year, across the single-path projection, strategy comparison, and Monte Carlo simulation (they all share `run_plan_projection()`).
- Every scenario predating this feature produces byte-for-byte identical output.
