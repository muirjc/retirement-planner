"""Unit tests for save_scenario() / list_scenarios() / load_scenario() (US2),
and delete_scenario() (007-bff-api-service research.md §1 -- added so the
BFF API Service feature can offer scenario removal over HTTP)."""

import pytest

from retirement_planner.scenario import (
    Account,
    Household,
    HouseholdMember,
    HsaContributionPlan,
    MarketAssumptions,
    Scenario,
    ScenarioParseError,
    SimulationSettings,
    SpendingProfile,
)
from retirement_planner.scenario.store import delete_scenario, list_scenarios, load_scenario, save_scenario


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


def test_hdhp_coverage_and_hsa_contribution_survive_a_save_load_round_trip(scenario_store_dir):
    """010-advanced-tax-benefits regression: _scenario_to_dict() builds its
    YAML dict field-by-field (not generically) and initially omitted both
    HouseholdMember.hdhp_coverage and Scenario.hsa_contribution -- silently
    dropping them on save, caught by a real BFF round-trip test before this
    core-level test was added to cover the actual source of the bug."""
    scenario = _scenario("hsa_case")
    scenario.household.members[0].hdhp_coverage = True
    scenario.hsa_contribution = HsaContributionPlan(annual_amount=3_000.0)

    save_scenario(scenario, scenarios_dir=scenario_store_dir)
    reloaded = load_scenario("hsa_case", scenarios_dir=scenario_store_dir)

    assert reloaded.household.members[0].hdhp_coverage is True
    assert reloaded.hsa_contribution == HsaContributionPlan(annual_amount=3_000.0)


def test_account_owner_survives_a_save_load_round_trip(scenario_store_dir):
    """011-per-owner-accounts regression: the same class of bug as the HSA
    one above -- _scenario_to_dict() initially omitted Account.owner,
    silently dropping ownership data on every save/load cycle, which would
    have made this feature non-functional in practice."""
    scenario = Scenario(
        name="couple",
        household=Household(
            filing_status="married_filing_jointly",
            members=[
                HouseholdMember(person_name="you", current_age=74, ss_claim_age=67, ss_annual_benefit=32_000.0),
                HouseholdMember(person_name="spouse", current_age=60, ss_claim_age=67, ss_annual_benefit=24_000.0),
            ],
        ),
        accounts=[
            Account(account_type="traditional", balance=900_000.0, owner="you"),
            Account(account_type="traditional", balance=300_000.0, owner="spouse"),
        ],
        spending=SpendingProfile(annual_need_real=90_000.0),
        state="GA",
        market_assumptions=_market_assumptions(),
        simulation_settings=SimulationSettings(n_paths=1000, seed=1, plan_to_age=95),
    )

    save_scenario(scenario, scenarios_dir=scenario_store_dir)
    reloaded = load_scenario("couple", scenarios_dir=scenario_store_dir)

    assert [a.owner for a in reloaded.accounts] == ["you", "spouse"]
    assert reloaded.is_usable


def test_single_member_account_owner_auto_fills_after_a_save_load_round_trip(scenario_store_dir):
    """A single-filer scenario saved with owner=None (the dataclass default,
    matching every scenario created before this feature) reloads with owner
    auto-filled -- no existing single-filer scenario file needs an edit."""
    scenario = _scenario("solo")
    assert scenario.accounts[0].owner is None

    save_scenario(scenario, scenarios_dir=scenario_store_dir)
    reloaded = load_scenario("solo", scenarios_dir=scenario_store_dir)

    assert reloaded.accounts[0].owner == "you"
    assert reloaded.is_usable


def test_hdhp_coverage_defaults_false_and_hsa_contribution_defaults_none(scenario_store_dir):
    """Every existing scenario (created before this feature) round-trips
    unchanged."""
    save_scenario(_scenario("no_hsa_case"), scenarios_dir=scenario_store_dir)
    reloaded = load_scenario("no_hsa_case", scenarios_dir=scenario_store_dir)

    assert reloaded.household.members[0].hdhp_coverage is False
    assert reloaded.hsa_contribution is None


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


def test_delete_scenario_removes_it_and_leaves_others_intact(scenario_store_dir):
    save_scenario(_scenario("keep_me"), scenarios_dir=scenario_store_dir)
    save_scenario(_scenario("delete_me"), scenarios_dir=scenario_store_dir)

    delete_scenario("delete_me", scenarios_dir=scenario_store_dir)

    assert list_scenarios(scenarios_dir=scenario_store_dir) == ["keep_me"]
    with pytest.raises(ScenarioParseError):
        load_scenario("delete_me", scenarios_dir=scenario_store_dir)


def test_delete_scenario_raises_the_same_error_shape_as_load_scenario_for_a_missing_name(scenario_store_dir):
    with pytest.raises(ScenarioParseError) as delete_exc_info:
        delete_scenario("never_saved", scenarios_dir=scenario_store_dir)

    with pytest.raises(ScenarioParseError) as load_exc_info:
        load_scenario("never_saved", scenarios_dir=scenario_store_dir)

    # Same exception type and the same "source" (the scenario name) --
    # confirms delete_scenario() mirrors load_scenario()'s existing
    # missing-scenario error shape exactly (research.md §1).
    assert type(delete_exc_info.value) is type(load_exc_info.value)
    assert delete_exc_info.value.source == load_exc_info.value.source == "never_saved"
