"""Scenarios page (User Story 1): create, save, re-load, and delete a
scenario entirely through the real form -- the one page this suite
drives field-by-field rather than seeding via a direct HTTP call, since
this page's own form is what's under test here.
"""

from __future__ import annotations

from helpers import fill_field, select_option, toggle_checkbox, wait_for_ready

_SCENARIO_NAME = "e2e_scenarios_page"


def _fill_minimal_single_filer(page, name: str) -> None:
    fill_field(page, "Scenario name", name)
    select_option(page, "Filing status", "single")
    fill_field(page, "Name", "alex")
    fill_field(page, "Current age", "60")
    fill_field(page, "SS claim age", "67")
    # 016-ss-claiming-age-actuarial-adjustment: relabeled from "SS annual
    # benefit ($)" -- it's now the member's PIA (benefit at full
    # retirement age), not the amount paid at the claim age above.
    fill_field(page, "SS benefit at FRA ($)", "20000")
    fill_field(page, "Traditional balance ($)", "800000")
    fill_field(page, "Roth balance ($)", "100000")
    fill_field(page, "Taxable balance ($)", "100000")
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


def test_create_save_and_reload_a_scenario(page, e2e_stack):
    page.goto(f"{e2e_stack.ui_base_url}/Scenarios", timeout=30_000)
    wait_for_ready(page)

    _fill_minimal_single_filer(page, _SCENARIO_NAME)
    page.get_by_role("button", name="Save", exact=True).click()

    success = page.get_by_test_id("stAlertContainer").filter(has_text=f"Saved '{_SCENARIO_NAME}'.")
    success.first.wait_for(state="visible", timeout=15_000)
    assert success.count() == 1

    # Reload the page fresh and load the just-saved scenario back in,
    # confirming the round trip through the real backend, not just that
    # the form's own session_state remembered what was typed.
    page.goto(f"{e2e_stack.ui_base_url}/Scenarios", timeout=30_000)
    wait_for_ready(page)
    select_option(page, "Saved scenarios", _SCENARIO_NAME)
    page.get_by_role("button", name="Load", exact=True).click()
    page.wait_for_timeout(1500)
    assert page.get_by_label("Current age", exact=True).input_value() == "60"


def test_a_negative_balance_is_rejected_with_a_blocking_flag(page, e2e_stack):
    """A save always persists (store.py's own "save and validate are
    orthogonal" contract -- Saved always shows), but a negative balance
    also surfaces its own blocking-flag message alongside it."""
    page.goto(f"{e2e_stack.ui_base_url}/Scenarios", timeout=30_000)
    wait_for_ready(page)

    _fill_minimal_single_filer(page, "e2e_invalid_scenario")
    fill_field(page, "Traditional balance ($)", "-1")
    page.get_by_role("button", name="Save", exact=True).click()

    negative_flag = page.get_by_test_id("stAlertContainer").filter(has_text="negative")
    negative_flag.first.wait_for(state="visible", timeout=15_000)
    assert negative_flag.count() >= 1


def test_include_an_inherited_ira_reveals_the_account_type_field(page, e2e_stack):
    """rp-c8b: the "Account type" selector (traditional/roth) added to
    this form -- previously the built account was hardcoded to
    traditional even though the engine now also supports Roth."""
    page.goto(f"{e2e_stack.ui_base_url}/Scenarios", timeout=30_000)
    wait_for_ready(page)

    toggle_checkbox(page, "Include an inherited IRA")
    account_type = page.get_by_role("combobox", name="Account type", exact=True)
    account_type.wait_for(state="visible", timeout=15_000)
    assert account_type.count() == 1
    select_option(page, "Account type", "roth")
    assert account_type.input_value() == "roth"
