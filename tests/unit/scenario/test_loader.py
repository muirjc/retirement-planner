"""Unit tests for parse_scenario() (US1)."""

import pytest

from retirement_planner.scenario import ScenarioParseError
from retirement_planner.scenario.loader import parse_scenario

FULL_SCENARIO_YAML = """
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
roth_conversion:
  strategy: fill_to_bracket
  bracket_ceiling_or_amount: 206700
  window: [2028, 2034]
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


def test_parse_scenario_happy_path_full_profile():
    scenario = parse_scenario(FULL_SCENARIO_YAML)

    assert scenario.name == "base_case"
    assert scenario.household.filing_status == "married_filing_jointly"
    assert [m.person_name for m in scenario.household.members] == ["you", "spouse"]
    assert scenario.household.members[0].ss_claim_age == 67
    assert [a.account_type for a in scenario.accounts] == ["traditional", "roth", "taxable"]
    assert scenario.accounts[0].balance == 1_500_000
    assert scenario.spending.annual_need_real == 110_000
    assert scenario.roth_conversion.strategy == "fill_to_bracket"
    assert scenario.roth_conversion.window == (2028, 2034)
    assert scenario.state == "GA"
    assert scenario.market_assumptions.equity_allocation == 0.60
    assert scenario.simulation_settings.n_paths == 5000
    assert scenario.simulation_settings.seed == 42
    assert scenario.simulation_settings.plan_to_age == 95
    # Loading alone doesn't run validation (that's validate()/load_scenario()'s job)
    assert scenario.validation_flags == []


def test_parse_scenario_name_override_parameter():
    scenario = parse_scenario(FULL_SCENARIO_YAML, name="renamed")
    assert scenario.name == "renamed"


def test_parse_scenario_reports_missing_required_field():
    yaml_text = FULL_SCENARIO_YAML.replace(
        "spending:\n  annual_need_real: 110000\n", ""
    )
    with pytest.raises(ScenarioParseError) as exc_info:
        parse_scenario(yaml_text)
    assert "spending" in exc_info.value.reason


def test_parse_scenario_raises_on_malformed_yaml():
    malformed = "name: base_case\nhousehold: [unclosed"
    with pytest.raises(ScenarioParseError):
        parse_scenario(malformed)


def test_parse_scenario_malformed_yaml_error_distinct_from_value_error():
    """A malformed file and a missing-field file both raise ScenarioParseError,
    but the reason text must differ so callers/logs can tell them apart."""
    malformed = "name: base_case\nhousehold: [unclosed"
    missing_field = FULL_SCENARIO_YAML.replace(
        "spending:\n  annual_need_real: 110000\n", ""
    )

    with pytest.raises(ScenarioParseError) as malformed_exc:
        parse_scenario(malformed)
    with pytest.raises(ScenarioParseError) as missing_exc:
        parse_scenario(missing_field)

    assert malformed_exc.value.reason != missing_exc.value.reason


def test_parse_scenario_raises_on_member_count_mismatch_single():
    yaml_text = FULL_SCENARIO_YAML.replace(
        "filing_status: married_filing_jointly", "filing_status: single"
    )
    with pytest.raises(ScenarioParseError) as exc_info:
        parse_scenario(yaml_text)
    assert "member" in exc_info.value.reason.lower()


def test_parse_scenario_auto_fills_owner_for_single_member_household():
    """011-per-owner-accounts: a single-member household is unambiguous --
    every account's owner is auto-filled from the sole member, with no
    `owner:` key required in the YAML (FR-003, research.md §3)."""
    yaml_text = """
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
  - account_type: roth
    balance: 100000
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
    scenario = parse_scenario(yaml_text, name="solo")
    assert [a.owner for a in scenario.accounts] == ["you", "you"]


def test_parse_scenario_leaves_owner_none_for_multi_member_household_when_omitted():
    """011-per-owner-accounts: a 2-member household is ambiguous -- an
    omitted `owner:` key parses as None rather than being guessed
    (FR-006); parse_scenario() never raises for this, only validate()
    flags it (research.md §3)."""
    scenario = parse_scenario(FULL_SCENARIO_YAML)
    assert [a.owner for a in scenario.accounts] == [None, None, None]


def test_parse_scenario_passes_through_explicit_owner():
    """011-per-owner-accounts: an explicitly-provided owner is passed
    through unchanged, for any household size."""
    yaml_text = FULL_SCENARIO_YAML.replace(
        "  - account_type: traditional\n    balance: 1500000\n",
        "  - account_type: traditional\n    balance: 1500000\n    owner: spouse\n",
    )
    scenario = parse_scenario(yaml_text)
    assert scenario.accounts[0].owner == "spouse"
    assert scenario.accounts[1].owner is None


def test_parse_scenario_raises_on_member_count_mismatch_mfj():
    single_member_yaml = """
name: single_person
household:
  filing_status: married_filing_jointly
  members:
    - person_name: you
      current_age: 60
      ss_claim_age: 67
      ss_annual_benefit: 32000
accounts:
  - account_type: traditional
    balance: 100000
spending:
  annual_need_real: 50000
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
  n_paths: 1000
  seed: 1
  plan_to_age: 90
"""
    with pytest.raises(ScenarioParseError):
        parse_scenario(single_member_yaml)


def test_parse_scenario_auto_fills_account_id_when_omitted():
    """012-inherited-ira-rmd: account_id is optional in the YAML -- when
    omitted, it's assigned deterministically from the account's own type
    and position (research.md §10), never a random value."""
    scenario = parse_scenario(FULL_SCENARIO_YAML)
    assert [a.account_id for a in scenario.accounts] == ["traditional-0", "roth-1", "taxable-2"]


def test_parse_scenario_passes_through_explicit_account_id():
    yaml_text = FULL_SCENARIO_YAML.replace(
        "  - account_type: traditional\n    balance: 1500000\n",
        "  - account_type: traditional\n    balance: 1500000\n    account_id: my-custom-id\n",
    )
    scenario = parse_scenario(yaml_text)
    assert scenario.accounts[0].account_id == "my-custom-id"
    assert scenario.accounts[1].account_id == "roth-1"


def test_parse_scenario_leaves_inherited_none_when_omitted():
    scenario = parse_scenario(FULL_SCENARIO_YAML)
    assert [a.inherited for a in scenario.accounts] == [None, None, None]


_INHERITED_ACCOUNT_YAML = """
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
      death_year: 2023
      decedent_age_at_death: 80
      decedent_was_taking_rmds: true
      beneficiary_relationship: other_individual
      beneficiary_classification: non_eligible_designated_beneficiary
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


def test_parse_scenario_parses_full_inherited_block():
    """012-inherited-ira-rmd: a present `inherited:` block parses into
    InheritedIraDetails with all five fields (data-model.md § InheritedIraDetails)."""
    scenario = parse_scenario(_INHERITED_ACCOUNT_YAML, name="inherited_case")
    inherited = scenario.accounts[0].inherited
    assert inherited is not None
    assert inherited.death_year == 2023
    assert inherited.decedent_age_at_death == 80
    assert inherited.decedent_was_taking_rmds is True
    assert inherited.beneficiary_relationship == "other_individual"
    assert inherited.beneficiary_classification == "non_eligible_designated_beneficiary"


@pytest.mark.parametrize(
    "missing_field",
    [
        "death_year: 2023\n",
        "decedent_age_at_death: 80\n",
        "decedent_was_taking_rmds: true\n",
        "beneficiary_relationship: other_individual\n",
        "beneficiary_classification: non_eligible_designated_beneficiary\n",
    ],
)
def test_parse_scenario_raises_when_inherited_block_missing_a_required_field(missing_field):
    """012-inherited-ira-rmd: an `inherited:` block, once present, requires
    every one of its five fields -- mirrors _build_roth_conversion()'s
    existing "present block, required inner fields" pattern (scenario-api.md)."""
    yaml_text = _INHERITED_ACCOUNT_YAML.replace(f"      {missing_field}", "")
    with pytest.raises(ScenarioParseError):
        parse_scenario(yaml_text, name="inherited_case")
