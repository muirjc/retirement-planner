"""Unit tests for validate() (US3)."""

from retirement_planner.scenario import (
    Account,
    Household,
    HouseholdMember,
    MarketAssumptions,
    Scenario,
    SimulationSettings,
    SpendingProfile,
)
from retirement_planner.scenario.validation import validate


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


def _member(name="you", age=60, claim_age=67, benefit=32_000.0):
    return HouseholdMember(
        person_name=name, current_age=age, ss_claim_age=claim_age, ss_annual_benefit=benefit
    )


def _clean_scenario(**overrides):
    defaults = dict(
        name="clean",
        household=Household(filing_status="single", members=[_member()]),
        accounts=[Account(account_type="traditional", balance=1_000_000.0)],
        spending=SpendingProfile(annual_need_real=50_000.0),
        state="GA",
        market_assumptions=_market_assumptions(),
        # plan_to_age matches the default member's current_age (60) so the
        # spending-vs-assets plausibility check has a 0-year horizon and
        # never fires unless a test explicitly sets up a longer horizon.
        simulation_settings=SimulationSettings(n_paths=1000, seed=1, plan_to_age=60),
    )
    defaults.update(overrides)
    return Scenario(**defaults)


def test_validate_flags_negative_account_balance_as_blocking():
    scenario = _clean_scenario(
        accounts=[Account(account_type="traditional", balance=-1_000.0)]
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "accounts[traditional].balance"
    assert flags[0].severity == "blocking"


def test_validate_flags_ss_claim_age_out_of_range_as_blocking():
    scenario = _clean_scenario(
        household=Household(filing_status="single", members=[_member(claim_age=75)])
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "household.members[0].ss_claim_age"
    assert flags[0].severity == "blocking"


def test_validate_accepts_ss_claim_age_boundaries_62_and_70():
    for boundary_age in (62, 70):
        scenario = _clean_scenario(
            household=Household(filing_status="single", members=[_member(claim_age=boundary_age)])
        )
        assert validate(scenario) == []


def test_validate_flags_negative_ss_annual_benefit_as_blocking():
    scenario = _clean_scenario(
        household=Household(filing_status="single", members=[_member(benefit=-500.0)])
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "household.members[0].ss_annual_benefit"
    assert flags[0].severity == "blocking"


def test_validate_flags_negative_spending_as_blocking():
    scenario = _clean_scenario(spending=SpendingProfile(annual_need_real=-1.0))
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "spending.annual_need_real"
    assert flags[0].severity == "blocking"


def test_validate_accepts_zero_spending():
    scenario = _clean_scenario(spending=SpendingProfile(annual_need_real=0.0))
    assert validate(scenario) == []


def test_validate_flags_spending_vs_assets_plausibility_as_warning_and_stays_usable():
    scenario = _clean_scenario(
        accounts=[Account(account_type="traditional", balance=50_000.0)],
        spending=SpendingProfile(annual_need_real=110_000.0),
        simulation_settings=SimulationSettings(n_paths=1000, seed=1, plan_to_age=95),
        household=Household(filing_status="single", members=[_member(age=60)]),
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "spending.annual_need_real"
    assert flags[0].severity == "warning"

    scenario.validation_flags = flags
    assert scenario.is_usable is True


def test_validate_returns_empty_list_for_clean_scenario():
    scenario = _clean_scenario()
    assert validate(scenario) == []
    scenario.validation_flags = validate(scenario)
    assert scenario.is_usable is True
