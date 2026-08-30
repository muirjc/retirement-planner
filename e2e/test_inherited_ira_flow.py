"""013-inherited-ira-edge-cases (rp-c8b, rp-iju, rp-l4d), built entirely
through the real Scenarios page form -- including the "Account type"
selector added for rp-c8b (previously the built account was hardcoded to
traditional) -- then run on both engines. Unit/BFF-level coverage for
the underlying computation already lives in tests/unit/mechanics/
test_inherited_rmd.py and services/bff/tests; this is the one place that
confirms a user can actually reach this case through the UI at all.
"""

from __future__ import annotations

from helpers import fill_field, select_option, select_radio, toggle_checkbox, wait_for_ready, wait_for_results

_SCENARIO_NAME = "e2e_inherited_roth_spouse_edb"


def test_build_a_roth_spouse_edb_inherited_account_and_run_both_engines(page, e2e_stack):
    page.goto(f"{e2e_stack.ui_base_url}/Scenarios", timeout=30_000)
    wait_for_ready(page)

    fill_field(page, "Scenario name", _SCENARIO_NAME)
    select_option(page, "Filing status", "married_filing_jointly")
    page.wait_for_timeout(500)

    # Both members' fields carry identical labels once married_filing_jointly
    # reveals member 2's row -- indexed (0 = member 1, 1 = member 2)
    # rather than fill_field()'s exact-label match, which would be
    # ambiguous with two members present.
    def fill_member_field(label: str, index: int, value: str) -> None:
        field = page.get_by_label(label, exact=True).nth(index)
        field.fill(value)
        field.blur()
        page.wait_for_timeout(150)

    fill_member_field("Name", 0, "you")
    fill_member_field("Current age", 0, "68")
    fill_member_field("SS claim age", 0, "67")
    fill_member_field("SS annual benefit ($)", 0, "30000")
    fill_member_field("Traditional balance ($)", 0, "500000")
    fill_member_field("Roth balance ($)", 0, "50000")
    fill_member_field("Taxable balance ($)", 0, "50000")

    fill_member_field("Name", 1, "spouse")
    fill_member_field("Current age", 1, "65")
    fill_member_field("SS claim age", 1, "67")
    fill_member_field("SS annual benefit ($)", 1, "20000")
    fill_member_field("Traditional balance ($)", 1, "0")
    fill_member_field("Roth balance ($)", 1, "0")
    fill_member_field("Taxable balance ($)", 1, "0")
    page.wait_for_timeout(300)

    toggle_checkbox(page, "Include an inherited IRA")
    select_option(page, "Account type", "roth")
    select_option(page, "Beneficiary", "spouse")
    fill_field(page, "Balance ($)", "200000")
    fill_field(page, "Decedent's death year", "2020")
    fill_field(page, "Decedent's age at death", "80")
    select_option(page, "Beneficiary relationship", "spouse")
    select_option(page, "Beneficiary classification", "eligible_designated_beneficiary_spouse")

    fill_field(page, "Annual spending need ($, today's dollars)", "40000")
    select_option(page, "State", "FL")
    fill_field(page, "Equity allocation", "0.6")
    fill_field(page, "Equity return mean (real)", "0.05")
    fill_field(page, "Equity return std (real)", "0.15")
    fill_field(page, "Correlation", "-0.2")
    fill_field(page, "Bond allocation", "0.4")
    fill_field(page, "Bond return mean (real)", "0.02")
    fill_field(page, "Bond return std (real)", "0.05")
    fill_field(page, "Paths", "100")
    fill_field(page, "Seed", "1")
    fill_field(page, "Plan to age", "90")

    page.get_by_role("button", name="Save", exact=True).click()
    success = page.get_by_test_id("stAlertContainer").filter(has_text=f"Saved '{_SCENARIO_NAME}'.")
    success.first.wait_for(state="visible", timeout=15_000)
    assert success.count() == 1

    # Run Simulation (Monte Carlo) -- rp-mt7 threaded inherited_accounts
    # through here; this scenario's own Roth/EDB account is what rp-iju/
    # rp-c8b newly make computable at all.
    page.goto(f"{e2e_stack.ui_base_url}/Run_Simulation", timeout=30_000)
    wait_for_ready(page)
    select_option(page, "Scenario", _SCENARIO_NAME)
    select_option(page, "Withdrawal strategy", "rmd_taxable_traditional_roth")
    fill_field(page, "Reference tax year", "2026")
    fill_field(page, "Start plan year", "1")
    fill_field(page, "Start tax year", "2026")
    page.get_by_role("button", name="Run", exact=True).click()
    wait_for_results(page)
    assert not page.get_by_test_id("stException").count()
    assert page.get_by_test_id("stMetric").count() == 1

    # Compare (Deterministic) -- US1/US2 of 012 already covered this
    # engine for the original non-EDB case; confirm it still works for
    # this newly-supported Roth/spouse-EDB combination too.
    page.goto(f"{e2e_stack.ui_base_url}/Compare", timeout=30_000)
    wait_for_ready(page)
    select_option(page, "Scenario", _SCENARIO_NAME)
    select_radio(page, "Deterministic")
    select_option(page, "Axis", "withdrawal_sequencing")
    fill_field(page, "Reference tax year", "2026")
    fill_field(page, "Start plan year", "1")
    fill_field(page, "Start tax year", "2026")
    fill_field(page, "Label", "default")
    select_option(page, "Withdrawal strategy", "rmd_taxable_traditional_roth")
    page.get_by_role("button", name="Compare", exact=True).click()
    wait_for_results(page)
    assert not page.get_by_test_id("stException").count()
    # 015-per-account-projection-detail: the summary table (1) plus one
    # per-candidate "Year-by-year detail" table (1) -- this comparison has
    # a single candidate ("default").
    assert page.get_by_test_id("stDataFrame").count() == 2
