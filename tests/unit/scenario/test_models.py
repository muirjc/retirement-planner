"""Unit tests for scenario dataclass construction and field access (US1)."""

from retirement_planner.scenario import (
    Account,
    Household,
    HouseholdMember,
    MarketAssumptions,
    RothConversionPlan,
    Scenario,
    SimulationSettings,
    SpendingProfile,
    ValidationFlag,
)


def _member(name="you", age=60, claim_age=67, benefit=32000.0):
    return HouseholdMember(
        person_name=name,
        current_age=age,
        ss_claim_age=claim_age,
        ss_annual_benefit=benefit,
    )


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


def test_household_member_fields_accessible_by_name():
    member = _member()
    assert member.person_name == "you"
    assert member.current_age == 60
    assert member.ss_claim_age == 67
    assert member.ss_annual_benefit == 32000.0


def test_household_supports_single_and_mfj_filing_status():
    single = Household(filing_status="single", members=[_member()])
    mfj = Household(
        filing_status="married_filing_jointly",
        members=[_member("you"), _member("spouse", age=58)],
    )
    assert len(single.members) == 1
    assert len(mfj.members) == 2


def test_account_fields_accessible_by_name():
    account = Account(account_type="traditional", balance=1_500_000.0)
    assert account.account_type == "traditional"
    assert account.balance == 1_500_000.0


def test_full_scenario_tree_builds_and_exposes_every_field():
    scenario = Scenario(
        name="base_case",
        household=Household(
            filing_status="married_filing_jointly",
            members=[_member("you"), _member("spouse", age=58, benefit=24000.0)],
        ),
        accounts=[
            Account(account_type="traditional", balance=1_500_000.0),
            Account(account_type="roth", balance=400_000.0),
            Account(account_type="taxable", balance=200_000.0),
        ],
        spending=SpendingProfile(annual_need_real=110_000.0),
        state="GA",
        market_assumptions=_market_assumptions(),
        simulation_settings=SimulationSettings(n_paths=5000, seed=42, plan_to_age=95),
        roth_conversion=RothConversionPlan(
            strategy="fill_to_bracket",
            bracket_ceiling_or_amount=206_700.0,
            window=(2028, 2034),
        ),
    )

    assert scenario.name == "base_case"
    assert scenario.household.members[0].person_name == "you"
    assert scenario.accounts[1].account_type == "roth"
    assert scenario.spending.annual_need_real == 110_000.0
    assert scenario.state == "GA"
    assert scenario.market_assumptions.equity_allocation == 0.6
    assert scenario.simulation_settings.plan_to_age == 95
    assert scenario.roth_conversion.strategy == "fill_to_bracket"
    assert scenario.roth_conversion.window == (2028, 2034)


def test_scenario_roth_conversion_defaults_to_none():
    scenario = Scenario(
        name="no_conversion",
        household=Household(filing_status="single", members=[_member()]),
        accounts=[Account(account_type="traditional", balance=100_000.0)],
        spending=SpendingProfile(annual_need_real=50_000.0),
        state="FL",
        market_assumptions=_market_assumptions(),
        simulation_settings=SimulationSettings(n_paths=1000, seed=1, plan_to_age=90),
    )
    assert scenario.roth_conversion is None
    assert scenario.validation_flags == []


def test_scenario_is_usable_true_with_no_blocking_flags():
    scenario = Scenario(
        name="clean",
        household=Household(filing_status="single", members=[_member()]),
        accounts=[Account(account_type="traditional", balance=100_000.0)],
        spending=SpendingProfile(annual_need_real=50_000.0),
        state="FL",
        market_assumptions=_market_assumptions(),
        simulation_settings=SimulationSettings(n_paths=1000, seed=1, plan_to_age=90),
        validation_flags=[
            ValidationFlag(field="spending.annual_need_real", message="plausibility note", severity="warning")
        ],
    )
    assert scenario.is_usable is True


def test_scenario_is_usable_false_with_a_blocking_flag():
    scenario = Scenario(
        name="broken",
        household=Household(filing_status="single", members=[_member()]),
        accounts=[Account(account_type="traditional", balance=-100.0)],
        spending=SpendingProfile(annual_need_real=50_000.0),
        state="FL",
        market_assumptions=_market_assumptions(),
        simulation_settings=SimulationSettings(n_paths=1000, seed=1, plan_to_age=90),
        validation_flags=[
            ValidationFlag(field="accounts[traditional].balance", message="negative balance", severity="blocking")
        ],
    )
    assert scenario.is_usable is False
