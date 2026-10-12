"""Performance check for the scenario configuration layer.

plan.md's Performance Goals: loading, saving, listing, or validating a
single scenario should complete in well under 1 second on a laptop. This is
a coarse smoke check, not a benchmark — it exists to catch an accidental
regression (e.g., an O(n^2) scan or an unintended network call), not to
micro-optimize.
"""

import time

from retirement_planner.scenario.loader import parse_scenario
from retirement_planner.scenario.store import list_scenarios, load_scenario, save_scenario
from retirement_planner.scenario.validation import validate

SCENARIO_YAML = """
name: perf_case
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
  asset_classes:
    us_large: {mean_real: 0.07, std_real: 0.18}
    us_small: {mean_real: 0.08, std_real: 0.22}
    us_medium: {mean_real: 0.075, std_real: 0.20}
    reit: {mean_real: 0.06, std_real: 0.20}
    aggregate_bond: {mean_real: 0.025, std_real: 0.06}
    emerging_market: {mean_real: 0.07, std_real: 0.25}
    international_ex_us: {mean_real: 0.06, std_real: 0.19}
    cash: {mean_real: 0.01, std_real: 0.01}
  correlation_matrix:
    - [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    - [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    - [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    - [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    - [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    - [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    - [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    - [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
taxable_allocation_schedule:
  periods:
    - start_plan_year: 1
      weights: {us_large: 0.125, us_small: 0.125, us_medium: 0.125, reit: 0.125, aggregate_bond: 0.125, emerging_market: 0.125, international_ex_us: 0.125, cash: 0.125}
traditional_allocation_schedule:
  periods:
    - start_plan_year: 1
      weights: {us_large: 0.125, us_small: 0.125, us_medium: 0.125, reit: 0.125, aggregate_bond: 0.125, emerging_market: 0.125, international_ex_us: 0.125, cash: 0.125}
roth_allocation_schedule:
  periods:
    - start_plan_year: 1
      weights: {us_large: 0.125, us_small: 0.125, us_medium: 0.125, reit: 0.125, aggregate_bond: 0.125, emerging_market: 0.125, international_ex_us: 0.125, cash: 0.125}
simulation_settings:
  n_paths: 5000
  seed: 42
  plan_to_age: 95
"""

# Generous budget: "well under 1 second" per plan.md, with headroom for slow CI runners.
_BUDGET_SECONDS = 1.0


def test_save_list_load_validate_complete_well_under_one_second(scenario_store_dir):
    scenario = parse_scenario(SCENARIO_YAML, name="perf_case")

    start = time.perf_counter()
    save_scenario(scenario, scenarios_dir=scenario_store_dir)
    list_scenarios(scenarios_dir=scenario_store_dir)
    loaded = load_scenario("perf_case", scenarios_dir=scenario_store_dir)
    validate(loaded)
    elapsed = time.perf_counter() - start

    assert elapsed < _BUDGET_SECONDS, (
        f"save+list+load+validate took {elapsed:.3f}s, expected < {_BUDGET_SECONDS}s"
    )
