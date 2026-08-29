"""Unit tests for src/rp_ui/instructions_content.py -- T002.

Checks the SECTIONS data directly rather than a rendered page, per
research.md §1's rationale: this is really "does this list of strings
contain these seven items," which doesn't need AppTest's overhead.
Every assertion here traces to a specific FR in spec.md / a row in
data-model.md's table.
"""

from rp_ui.instructions_content import SECTIONS, Section

REQUIRED_TITLES = {
    "Household",
    "Accounts",
    "Spending",
    "State",
    "Market Assumptions",
    "Simulation Settings",
    "Roth Conversion (Optional)",
    "Inherited IRA (Optional)",
    "Run Simulation",
    "Compare",
}


def test_all_ten_sections_are_present():
    """FR-002, SC-002: 10 of 10 field-groups covered (7 Scenarios-form
    groups, the Scenarios-form Inherited IRA block, plus the Run
    Simulation and Compare pages)."""
    assert {section.title for section in SECTIONS} == REQUIRED_TITLES
    assert len(SECTIONS) == 10


def test_sections_are_the_documented_dataclass_shape():
    for section in SECTIONS:
        assert isinstance(section, Section)
        assert isinstance(section.title, str) and section.title
        assert isinstance(section.body, str) and section.body


def _body_for(title: str) -> str:
    return next(section.body for section in SECTIONS if section.title == title)


def test_accounts_section_states_balances_are_entered_per_party():
    """011-per-owner-accounts: supersedes the pre-011 pooled-balance
    guidance this section used to give (now actively wrong -- accounts
    are captured per owner, not combined, so RMDs can be computed
    accurately per person)."""
    body = _body_for("Accounts")
    assert "own balance" in body
    assert "per person" in body


def test_household_section_states_benefit_must_match_claiming_age():
    """FR-004."""
    body = _body_for("Household")
    assert "claiming age" in body
    assert "full retirement age" in body


def test_spending_section_states_todays_dollars_and_pre_tax():
    """FR-005."""
    body = _body_for("Spending")
    assert "today's dollars" in body
    assert "before taxes" in body


def test_state_section_names_no_specific_state_code():
    """FR-006, SC-004 -- never enumerate the supported list here, or this
    content silently goes stale the next time a state module is added."""
    body = _body_for("State")
    for code in ("SC", "DE", "FL"):
        assert code not in body
    assert "dropdown" in body


def test_market_assumptions_section_frames_examples_as_examples():
    """FR-007."""
    body = _body_for("Market Assumptions")
    assert "example" in body.lower()
    assert "not a fact" in body.lower() or "not a recommendation" in body.lower()


def test_simulation_settings_section_explains_paths_seed_and_plan_to_age():
    body = _body_for("Simulation Settings")
    assert "Paths" in body
    assert "Seed" in body
    assert "Plan to age" in body
    assert "not a prediction" in body


def test_roth_conversion_section_explains_window():
    body = _body_for("Roth Conversion (Optional)")
    assert "window" in body.lower()
    assert "plan years" in body


def test_run_simulation_section_warns_about_reference_tax_year_placeholder():
    """Reflects a real prior bug: an unedited reference_tax_year placeholder
    (e.g. left at 1900) surfaced as a bare HTTP 500 before being fixed --
    see rp_ui/errors.py's UnsupportedTaxYearError handling."""
    body = _body_for("Run Simulation")
    assert "reference tax year" in body.lower()
    assert "placeholder" in body.lower()


def test_run_simulation_section_explains_override_checkbox_gates_advanced_fields():
    body = _body_for("Run Simulation")
    assert "Override scenario defaults" in body
    assert "otherwise ignored" in body.lower()


def test_household_section_explains_filing_status_options():
    body = _body_for("Household")
    assert "`single`" in body
    assert "`married_filing_jointly`" in body


def test_run_simulation_section_explains_both_withdrawal_strategy_options():
    body = _body_for("Run Simulation")
    assert "`rmd_taxable_traditional_roth`" in body
    assert "`rmd_traditional_taxable_roth`" in body


def test_roth_conversion_section_explains_both_conversion_strategy_options():
    body = _body_for("Roth Conversion (Optional)")
    assert "`fill_to_bracket`" in body
    assert "`fixed_amount`" in body
    assert "ceiling" in body.lower()


def test_state_section_explains_general_differences_without_naming_a_state():
    """Explains what a user should expect to differ between states without
    naming a specific state code, so this content never goes stale as
    states are added (test_state_section_names_no_specific_state_code
    above already guards the no-hardcoded-list rule)."""
    body = _body_for("State")
    assert "exclusion" in body.lower()
    assert "no state income tax" in body.lower() or "tax income at all" in body.lower()


def test_compare_section_explains_both_engine_options():
    body = _body_for("Compare")
    assert "Monte Carlo" in body
    assert "Deterministic" in body


def test_compare_section_explains_all_four_axis_options():
    body = _body_for("Compare")
    for axis in ("`state`", "`roth_conversion_strategy`", "`withdrawal_sequencing`", "`claiming_age_grid`"):
        assert axis in body


def test_inherited_ira_section_explains_supported_case_and_every_field():
    body = _body_for("Inherited IRA (Optional)")
    assert "10-year rule" in body
    assert "`non_eligible_designated_beneficiary`" in body
    assert "never legally combined" in body.lower() or "tracked completely separately" in body.lower()
    for field in ("Beneficiary", "Balance", "Decedent's death year", "Decedent's age at death"):
        assert field in body
