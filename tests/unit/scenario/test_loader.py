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


def test_parse_scenario_defaults_full_retirement_age_to_claim_age_when_omitted():
    # 016-ss-claiming-age-actuarial-adjustment: FULL_SCENARIO_YAML above
    # never sets full_retirement_age -- every member should resolve to
    # their own ss_claim_age (research.md Decision 3), never None.
    scenario = parse_scenario(FULL_SCENARIO_YAML)
    assert scenario.household.members[0].full_retirement_age == 67.0
    assert scenario.household.members[1].full_retirement_age == 67.0


def test_parse_scenario_passes_through_explicit_full_retirement_age():
    yaml_text = FULL_SCENARIO_YAML.replace(
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n",
        "      ss_claim_age: 62\n      ss_annual_benefit: 32000\n      full_retirement_age: 67.0\n",
        1,
    )
    scenario = parse_scenario(yaml_text)
    assert scenario.household.members[0].ss_claim_age == 62
    assert scenario.household.members[0].full_retirement_age == 67.0
    # The second member still gets the default -- explicit FRA is per-member.
    assert scenario.household.members[1].full_retirement_age == 67.0


def test_parse_scenario_defaults_predicted_death_age_to_none_when_omitted():
    # 017-ss-spousal-survivor-benefits: FULL_SCENARIO_YAML above never sets
    # predicted_death_age -- unlike full_retirement_age, None here is
    # already the fully-meaningful "no hypothetical death configured"
    # value, not a placeholder resolved to some other default.
    scenario = parse_scenario(FULL_SCENARIO_YAML)
    assert scenario.household.members[0].predicted_death_age is None
    assert scenario.household.members[1].predicted_death_age is None


def test_parse_scenario_passes_through_explicit_predicted_death_age():
    yaml_text = FULL_SCENARIO_YAML.replace(
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n",
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n      predicted_death_age: 85\n",
        1,
    )
    scenario = parse_scenario(yaml_text)
    assert scenario.household.members[0].predicted_death_age == 85
    # The second member still gets the default -- explicit value is per-member.
    assert scenario.household.members[1].predicted_death_age is None


def test_parse_scenario_defaults_income_streams_to_empty_list_when_omitted():
    # 021-pension-annuity-income (rp-pid): FULL_SCENARIO_YAML above never
    # sets income_streams -- every scenario predating this feature should
    # round-trip to an empty list, not None or a missing attribute.
    scenario = parse_scenario(FULL_SCENARIO_YAML)
    assert scenario.household.members[0].income_streams == []
    assert scenario.household.members[1].income_streams == []


def test_parse_scenario_passes_through_income_streams():
    yaml_text = FULL_SCENARIO_YAML.replace(
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n",
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n"
        "      income_streams:\n"
        "        - label: State Pension\n"
        "          stream_type: pension\n"
        "          start_age: 62\n"
        "          annual_amount: 18000\n"
        "          inflation_adjustment: cola_adjusted\n"
        "        - label: Old annuity\n"
        "          stream_type: annuity\n"
        "          start_age: 65\n"
        "          end_age: 74\n"
        "          annual_amount: 6000\n"
        "          inflation_adjustment: fixed_nominal\n",
        1,
    )
    scenario = parse_scenario(yaml_text)
    streams = scenario.household.members[0].income_streams
    assert len(streams) == 2
    assert streams[0].label == "State Pension"
    assert streams[0].stream_type == "pension"
    assert streams[0].start_age == 62
    assert streams[0].end_age is None
    assert streams[0].annual_amount == 18000
    assert streams[0].inflation_adjustment == "cola_adjusted"
    assert streams[1].end_age == 74
    assert streams[1].inflation_adjustment == "fixed_nominal"
    # 027-nc-bailey-exclusion: bailey_qualifying defaults to False when omitted.
    assert streams[0].bailey_qualifying is False
    assert streams[1].bailey_qualifying is False
    # The second member still gets the default -- income_streams is per-member.
    assert scenario.household.members[1].income_streams == []


def test_parse_scenario_passes_through_bailey_qualifying():
    # 027-nc-bailey-exclusion: an explicit bailey_qualifying: true is read through.
    yaml_text = FULL_SCENARIO_YAML.replace(
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n",
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n"
        "      income_streams:\n"
        "        - label: State Pension\n"
        "          stream_type: pension\n"
        "          start_age: 62\n"
        "          annual_amount: 18000\n"
        "          inflation_adjustment: cola_adjusted\n"
        "          bailey_qualifying: true\n",
        1,
    )
    scenario = parse_scenario(yaml_text)
    assert scenario.household.members[0].income_streams[0].bailey_qualifying is True


def test_parse_scenario_income_stream_missing_required_field_raises():
    yaml_text = FULL_SCENARIO_YAML.replace(
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n",
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n"
        "      income_streams:\n"
        "        - label: Missing start_age\n"
        "          stream_type: pension\n"
        "          annual_amount: 18000\n"
        "          inflation_adjustment: cola_adjusted\n",
        1,
    )
    with pytest.raises(ScenarioParseError) as excinfo:
        parse_scenario(yaml_text)
    assert "start_age" in str(excinfo.value)


def test_parse_scenario_income_stream_label_defaults_to_empty_string():
    yaml_text = FULL_SCENARIO_YAML.replace(
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n",
        "      ss_claim_age: 67\n      ss_annual_benefit: 32000\n"
        "      income_streams:\n"
        "        - stream_type: earned_income\n"
        "          start_age: 63\n"
        "          annual_amount: 25000\n"
        "          inflation_adjustment: fixed_nominal\n",
        1,
    )
    scenario = parse_scenario(yaml_text)
    assert scenario.household.members[0].income_streams[0].label == ""


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
