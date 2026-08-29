"""Integration tests for the full scenario lifecycle: author -> save -> list
-> load -> validate. Sections are added incrementally as each user story is
implemented (US1, then US2, then US3), then Phase 6 adds cross-cutting checks
and the full quickstart.md walkthrough.
"""

from dataclasses import replace

import pytest

from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection
from retirement_planner.mechanics import compute_rmd
from retirement_planner.scenario.loader import ScenarioParseError, parse_scenario
from retirement_planner.scenario.store import list_scenarios, load_scenario, save_scenario

BASE_CASE_YAML = """
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
    owner: you
  - account_type: roth
    balance: 400000
    owner: you
  - account_type: taxable
    balance: 200000
    owner: spouse
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
"""


# ---------------------------------------------------------------------------
# User Story 1: Describe a retirement scenario without touching code
# ---------------------------------------------------------------------------


def test_us1_full_profile_loads_into_structured_representation():
    """Acceptance Scenario 1.1: every authored field is present and typed."""
    scenario = parse_scenario(BASE_CASE_YAML, name="base_case")

    assert scenario.name == "base_case"
    assert scenario.household.filing_status == "married_filing_jointly"
    assert len(scenario.household.members) == 2
    assert scenario.accounts[0].balance == 1_500_000
    assert scenario.spending.annual_need_real == 110_000
    assert scenario.state == "GA"
    assert scenario.market_assumptions.equity_allocation == 0.60
    assert scenario.simulation_settings.plan_to_age == 95


def test_us1_changing_one_value_and_reparsing_changes_only_that_field():
    """Acceptance Scenario 1.3: a single-value edit reflects in isolation."""
    original = parse_scenario(BASE_CASE_YAML, name="base_case")

    edited_yaml = BASE_CASE_YAML.replace(
        "  annual_need_real: 110000\n", "  annual_need_real: 160000\n"
    )
    edited = parse_scenario(edited_yaml, name="base_case")

    assert edited.spending.annual_need_real == 160_000
    assert original.spending.annual_need_real == 110_000
    # Everything else is unchanged
    assert edited.household == original.household
    assert edited.accounts == original.accounts
    assert edited.state == original.state
    assert edited.market_assumptions == original.market_assumptions
    assert edited.simulation_settings == original.simulation_settings


# ---------------------------------------------------------------------------
# User Story 2: Maintain multiple named scenarios for comparison
# ---------------------------------------------------------------------------


def test_us2_save_list_reload_two_named_scenarios_stay_isolated(scenario_store_dir):
    """Acceptance Scenarios 2.1-2.3, SC-003."""
    base_case = parse_scenario(BASE_CASE_YAML, name="base_case")
    save_scenario(base_case, scenarios_dir=scenario_store_dir)

    high_spending = replace(
        base_case,
        name="high_spending",
        spending=replace(base_case.spending, annual_need_real=160_000.0),
    )
    save_scenario(high_spending, scenarios_dir=scenario_store_dir)

    assert sorted(list_scenarios(scenarios_dir=scenario_store_dir)) == [
        "base_case",
        "high_spending",
    ]

    # base_case is untouched by the high_spending save (FR-005).
    reloaded_base = load_scenario("base_case", scenarios_dir=scenario_store_dir)
    assert reloaded_base.spending.annual_need_real == 110_000.0

    reloaded_high = load_scenario("high_spending", scenarios_dir=scenario_store_dir)
    assert reloaded_high.spending.annual_need_real == 160_000.0


# ---------------------------------------------------------------------------
# User Story 3: Catch impossible or out-of-range inputs before they're used
# ---------------------------------------------------------------------------

BROKEN_SCENARIO_YAML = """
name: broken
household:
  filing_status: single
  members:
    - person_name: you
      current_age: 60
      ss_claim_age: 75
      ss_annual_benefit: 32000
accounts:
  - account_type: traditional
    balance: -1000
spending:
  annual_need_real: 110000
state: GA
market_assumptions:
  equity_allocation: 0.6
  equity_return_mean_real: 0.065
  equity_return_std_real: 0.17
  bond_allocation: 0.4
  bond_return_mean_real: 0.015
  bond_return_std_real: 0.06
  correlation: -0.10
simulation_settings:
  n_paths: 5000
  seed: 42
  plan_to_age: 95
"""


def test_us3_multiple_simultaneous_problems_all_reported_together(scenario_store_dir):
    """Acceptance Scenarios 3.1-3.3, FR-006, FR-011: both impossible-value
    problems are reported in one pass, each naming its own field and reason,
    and each is blocking (which alone is enough to make is_usable False).
    BROKEN_SCENARIO_YAML's spending/horizon numbers also legitimately trip
    the spending-vs-assets plausibility warning (see quickstart.md step 2) —
    that's expected and doesn't change the outcome, since is_usable only
    cares about blocking flags; this test checks the two impossible-value
    flags specifically rather than asserting every flag is blocking."""
    (scenario_store_dir / "broken.yaml").write_text(BROKEN_SCENARIO_YAML)

    broken = load_scenario("broken", scenarios_dir=scenario_store_dir)

    assert not broken.is_usable
    by_field = {flag.field: flag.severity for flag in broken.validation_flags}
    assert by_field["household.members[0].ss_claim_age"] == "blocking"
    assert by_field["accounts[traditional].balance"] == "blocking"
    assert all(flag.message for flag in broken.validation_flags)  # every flag names a reason


CLEAN_CASE_YAML = """
name: clean_case
household:
  filing_status: single
  members:
    - person_name: you
      current_age: 60
      ss_claim_age: 67
      ss_annual_benefit: 32000
accounts:
  - account_type: traditional
    balance: 500000
spending:
  annual_need_real: 50000
state: GA
market_assumptions:
  equity_allocation: 0.6
  equity_return_mean_real: 0.065
  equity_return_std_real: 0.17
  bond_allocation: 0.4
  bond_return_mean_real: 0.015
  bond_return_std_real: 0.06
  correlation: -0.10
simulation_settings:
  n_paths: 5000
  seed: 42
  plan_to_age: 60
"""


def test_us3_clean_scenario_raises_no_flags(scenario_store_dir):
    """Acceptance Scenario 3.4. Uses a 0-year horizon (plan_to_age ==
    current_age) so the spending-vs-assets plausibility check can't fire —
    see quickstart.md step 4's clean_case example."""
    save_scenario(parse_scenario(CLEAN_CASE_YAML, name="clean_case"), scenarios_dir=scenario_store_dir)
    scenario = load_scenario("clean_case", scenarios_dir=scenario_store_dir)
    assert scenario.validation_flags == []
    assert scenario.is_usable is True


# ---------------------------------------------------------------------------
# Phase 6: Polish & cross-cutting concerns
# ---------------------------------------------------------------------------


def test_malformed_file_raises_parse_error_not_a_validation_flag(scenario_store_dir):
    """FR-012: a file that can't be parsed at all is a ScenarioParseError,
    never surfaced as a ValidationFlag on some partially-built Scenario."""
    (scenario_store_dir / "unparseable.yaml").write_text("name: base_case\nhousehold: [unclosed")

    with pytest.raises(ScenarioParseError):
        load_scenario("unparseable", scenarios_dir=scenario_store_dir)


def test_single_member_household_rmd_is_a_no_op_relative_to_compute_rmd(scenario_store_dir):
    """011-per-owner-accounts FR-009/SC-004 regression parity: a single-
    filer scenario's owner is auto-filled (share=1.0) with zero action
    from the user (research.md §3), and that share must be a pure no-op --
    the RMD run_plan_projection() computes must be byte-identical to
    calling compute_rmd() directly against the member's full, unscaled
    balance and age. This is the guarantee that lets every single-filer
    scenario that predates this feature keep producing identical output."""
    solo_yaml = """
name: solo_rmd_case
household:
  filing_status: single
  members:
    - person_name: you
      current_age: 75
      ss_claim_age: 67
      ss_annual_benefit: 32000
accounts:
  - account_type: traditional
    balance: 1000000
spending:
  annual_need_real: 60000
state: FL
market_assumptions:
  equity_allocation: 0.6
  equity_return_mean_real: 0.065
  equity_return_std_real: 0.17
  bond_allocation: 0.4
  bond_return_mean_real: 0.015
  bond_return_std_real: 0.06
  correlation: -0.10
simulation_settings:
  n_paths: 1
  seed: 1
  plan_to_age: 75
"""
    scenario = parse_scenario(solo_yaml, name="solo_rmd_case")
    save_scenario(scenario, scenarios_dir=scenario_store_dir)
    reloaded = load_scenario("solo_rmd_case", scenarios_dir=scenario_store_dir)

    assert reloaded.accounts[0].owner == "you"  # auto-filled, no user action (FR-003)
    assert reloaded.is_usable

    from retirement_planner.mechanics import AccountBalances

    accounts = AccountBalances(
        traditional=sum(a.balance for a in reloaded.accounts if a.account_type == "traditional"),
        roth=0.0,
        taxable=0.0,
    )
    strategy = StrategyConfiguration(
        label="solo", withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
        claiming_ages={"you": reloaded.household.members[0].ss_claim_age},
    )
    projection = run_plan_projection(
        household=reloaded.household, accounts=accounts,
        traditional_ownership_shares={"you": 1.0},  # the sole member's auto-filled share
        annual_spending_need=reloaded.spending.annual_need_real, state=reloaded.state,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026,
        plan_to_age=reloaded.simulation_settings.plan_to_age, strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    expected_rmd = compute_rmd(
        traditional_balance=accounts.traditional, member_age=75, tax_year=2026,
        spouse_age=None, spouse_is_sole_beneficiary=False,
    )
    assert projection.years[0].mechanics.withdrawal_plan.rmd_drawn == pytest.approx(expected_rmd.required_amount)


def test_quickstart_walkthrough_end_to_end(scenario_store_dir):
    """Runs every step of quickstart.md as one sequence, confirming the
    feature works end-to-end exactly as documented for a new user."""
    # Step 1 + 2: author and load base_case; it carries a plausibility
    # warning (spending-vs-assets doesn't offset for Social Security) but
    # stays usable.
    base_case = parse_scenario(BASE_CASE_YAML, name="base_case")
    save_scenario(base_case, scenarios_dir=scenario_store_dir)
    reloaded_base = load_scenario("base_case", scenarios_dir=scenario_store_dir)
    assert reloaded_base.household.members[0].person_name == "you"
    assert reloaded_base.is_usable
    assert any(f.severity == "warning" for f in reloaded_base.validation_flags)

    # Step 3: save a second named scenario; base_case stays untouched.
    high_spending = replace(
        reloaded_base,
        name="high_spending",
        spending=replace(reloaded_base.spending, annual_need_real=160_000.0),
    )
    save_scenario(high_spending, scenarios_dir=scenario_store_dir)
    assert sorted(list_scenarios(scenarios_dir=scenario_store_dir)) == [
        "base_case",
        "high_spending",
    ]
    assert load_scenario("base_case", scenarios_dir=scenario_store_dir).spending.annual_need_real == 110_000.0

    # Step 4: a scenario with two impossible values is flagged, and a
    # scenario with none raises no flags at all.
    (scenario_store_dir / "broken.yaml").write_text(BROKEN_SCENARIO_YAML)
    broken = load_scenario("broken", scenarios_dir=scenario_store_dir)
    assert not broken.is_usable
    by_field = {f.field: f.severity for f in broken.validation_flags}
    assert by_field["household.members[0].ss_claim_age"] == "blocking"
    assert by_field["accounts[traditional].balance"] == "blocking"

    save_scenario(parse_scenario(CLEAN_CASE_YAML, name="clean_case"), scenarios_dir=scenario_store_dir)
    clean = load_scenario("clean_case", scenarios_dir=scenario_store_dir)
    assert clean.validation_flags == []

    # Step 5: a malformed file is a parse error, distinct from a scenario
    # that parses but carries blocking flags.
    (scenario_store_dir / "unparseable.yaml").write_text("name: base_case\nhousehold: [unclosed")
    with pytest.raises(ScenarioParseError):
        load_scenario("unparseable", scenarios_dir=scenario_store_dir)
