"""Unit tests for save_scenario() / list_scenarios() / load_scenario() (US2)."""

from retirement_planner.scenario import (
    Account,
    Household,
    HouseholdMember,
    MarketAssumptions,
    Scenario,
    SimulationSettings,
    SpendingProfile,
)
from retirement_planner.scenario.store import list_scenarios, load_scenario, save_scenario


def _market_assumptions():
    return MarketAssumptions(
        equity_allocation=0.6,
        equity_return_mean_real=0.065,
        equity_return_std_real=0.17,
        bond_allocation=0.4,
        bond_return_mean_real=0.015,
        bond_return_std_real=0.06,
        correlation=-0.10,
    )


def _scenario(name, spending=110_000.0):
    return Scenario(
        name=name,
        household=Household(
            filing_status="single",
            members=[
                HouseholdMember(
                    person_name="you",
                    current_age=60,
                    ss_claim_age=67,
                    ss_annual_benefit=32_000.0,
                )
            ],
        ),
        accounts=[Account(account_type="traditional", balance=1_000_000.0)],
        spending=SpendingProfile(annual_need_real=spending),
        state="GA",
        market_assumptions=_market_assumptions(),
        simulation_settings=SimulationSettings(n_paths=1000, seed=1, plan_to_age=90),
    )


def test_save_list_load_round_trip_for_ten_scenarios_stays_isolated(scenario_store_dir):
    names = [f"scenario_{i}" for i in range(10)]
    for i, name in enumerate(names):
        save_scenario(_scenario(name, spending=100_000.0 + i), scenarios_dir=scenario_store_dir)

    listed = list_scenarios(scenarios_dir=scenario_store_dir)
    assert sorted(listed) == sorted(names)

    for i, name in enumerate(names):
        reloaded = load_scenario(name, scenarios_dir=scenario_store_dir)
        assert reloaded.name == name
        assert reloaded.spending.annual_need_real == 100_000.0 + i

    # Editing/reloading one scenario's saved data doesn't touch any other's.
    edited = _scenario(names[3], spending=999_999.0)
    save_scenario(edited, scenarios_dir=scenario_store_dir)
    for i, name in enumerate(names):
        reloaded = load_scenario(name, scenarios_dir=scenario_store_dir)
        expected = 999_999.0 if i == 3 else 100_000.0 + i
        assert reloaded.spending.annual_need_real == expected


def test_save_scenario_overwrites_existing_name(scenario_store_dir):
    save_scenario(_scenario("base_case", spending=110_000.0), scenarios_dir=scenario_store_dir)
    save_scenario(_scenario("base_case", spending=160_000.0), scenarios_dir=scenario_store_dir)

    assert list_scenarios(scenarios_dir=scenario_store_dir) == ["base_case"]
    reloaded = load_scenario("base_case", scenarios_dir=scenario_store_dir)
    assert reloaded.spending.annual_need_real == 160_000.0
