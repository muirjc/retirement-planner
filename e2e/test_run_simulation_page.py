"""Run Simulation page (User Story 2, plus rp-r07's results explanation
and the verification indicator). Seeds its scenario via a direct HTTP
call to this suite's own isolated BFF instance -- this file is about the
Run Simulation page itself, not re-testing the Scenarios page's form
(covered in test_scenarios_page.py).
"""

from __future__ import annotations

import httpx

from helpers import fill_field, select_option, wait_for_ready, wait_for_results

_SCENARIO_NAME = "e2e_run_simulation"

_SCENARIO_BODY = {
    "household": {
        "filing_status": "married_filing_jointly",
        "members": [
            {"person_name": "you", "current_age": 60, "ss_claim_age": 67, "ss_annual_benefit": 30_000},
            {"person_name": "spouse", "current_age": 58, "ss_claim_age": 67, "ss_annual_benefit": 20_000},
        ],
    },
    "accounts": [
        {"account_type": "traditional", "balance": 1_200_000, "owner": "you"},
        {"account_type": "roth", "balance": 200_000, "owner": "you"},
        {"account_type": "taxable", "balance": 100_000, "owner": "spouse"},
    ],
    "spending": {"annual_need_real": 70_000},
    "state": "FL",
    "market_assumptions": {
        "equity_allocation": 0.60, "equity_return_mean_real": 0.065, "equity_return_std_real": 0.17,
        "bond_allocation": 0.40, "bond_return_mean_real": 0.015, "bond_return_std_real": 0.06,
        "correlation": -0.10,
    },
    "simulation_settings": {"n_paths": 200, "seed": 42, "plan_to_age": 95},
}


def _seed_scenario(bff_base_url: str) -> None:
    response = httpx.put(f"{bff_base_url}/scenarios/{_SCENARIO_NAME}", json=_SCENARIO_BODY, timeout=30.0)
    response.raise_for_status()
    assert response.json()["is_usable"] is True


def test_run_shows_success_rate_fan_chart_explanation_and_verification(page, e2e_stack):
    _seed_scenario(e2e_stack.bff_base_url)

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
    assert "Success rate" in page.get_by_test_id("stMetric").inner_text()
    assert page.locator('[data-testid="stPlotlyChart"]').count() == 1
    # rp-r07: the numbers-behind-the-chart explanation, collapsed by default.
    assert page.get_by_text("How were these numbers computed?").count() == 1
    # 006/US4: the verification indicator, always rendered one way or the other.
    alerts_text = page.get_by_test_id("stAlertContainer").all_inner_texts()
    assert any("verified" in text.lower() for text in alerts_text)


def test_prepare_csv_download_produces_a_download_button(page, e2e_stack):
    _seed_scenario(e2e_stack.bff_base_url)

    page.goto(f"{e2e_stack.ui_base_url}/Run_Simulation", timeout=30_000)
    wait_for_ready(page)

    select_option(page, "Scenario", _SCENARIO_NAME)
    select_option(page, "Withdrawal strategy", "rmd_taxable_traditional_roth")
    fill_field(page, "Reference tax year", "2026")
    fill_field(page, "Start plan year", "1")
    fill_field(page, "Start tax year", "2026")
    page.get_by_role("button", name="Run", exact=True).click()
    wait_for_results(page)

    page.get_by_role("button", name="Prepare CSV download", exact=True).click()
    download_button = page.get_by_role("button", name="Download CSV", exact=True)
    download_button.wait_for(state="visible", timeout=15_000)
    assert download_button.count() == 1
