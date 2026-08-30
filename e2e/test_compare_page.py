"""Compare page (User Story 3): every axis, on every engine that
supports it -- state is Monte Carlo-only (FR-010, enforced client-side),
the other three axes run on both engines.
"""

from __future__ import annotations

import httpx
import pytest

from helpers import fill_field, select_option, select_radio, wait_for_ready, wait_for_results

_SCENARIO_NAME = "e2e_compare"

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
    "simulation_settings": {"n_paths": 100, "seed": 42, "plan_to_age": 95},
}


@pytest.fixture(scope="module", autouse=True)
def _seed_scenario(e2e_stack):
    response = httpx.put(f"{e2e_stack.bff_base_url}/scenarios/{_SCENARIO_NAME}", json=_SCENARIO_BODY, timeout=30.0)
    response.raise_for_status()
    assert response.json()["is_usable"] is True


def _fill_candidate_fields(page, axis: str) -> None:
    if axis == "state":
        select_option(page, "State", "FL")
    elif axis == "roth_conversion_strategy":
        fill_field(page, "Label", "candidate_a")
        select_option(page, "Conversion strategy", "fill_to_bracket")
        fill_field(page, "Bracket ceiling/amount ($)", "100000")
        fill_field(page, "Window start", "1")
        fill_field(page, "Window end", "5")
    elif axis == "withdrawal_sequencing":
        fill_field(page, "Label", "candidate_a")
        select_option(page, "Withdrawal strategy", "rmd_taxable_traditional_roth")
    elif axis == "claiming_age_grid":
        # rp-dd9: a married household's candidate must name every member
        # -- Person 2 left blank previously 500'd, not merely produced a
        # single-earner result.
        fill_field(page, "Person 1 name", "you")
        fill_field(page, "Person 1 claim age", "67")
        fill_field(page, "Person 2 name (optional)", "spouse")
        fill_field(page, "Person 2 claim age", "67")
    else:
        raise AssertionError(f"unhandled axis {axis!r}")


def _run_one_compare(page, e2e_stack, *, engine: str, axis: str) -> None:
    page.goto(f"{e2e_stack.ui_base_url}/Compare", timeout=30_000)
    wait_for_ready(page)

    select_option(page, "Scenario", _SCENARIO_NAME)
    select_radio(page, engine)
    select_option(page, "Axis", axis)
    fill_field(page, "Reference tax year", "2026")
    fill_field(page, "Start plan year", "1")
    fill_field(page, "Start tax year", "2026")
    _fill_candidate_fields(page, axis)

    page.get_by_role("button", name="Compare", exact=True).click()
    wait_for_results(page)

    assert not page.get_by_test_id("stException").count(), page.content()
    assert page.locator('[data-testid="stPlotlyChart"]').count() == 1
    assert page.get_by_test_id("stDataFrame").count() == 1
    # rp-r07: one results-explanation expander per candidate (one
    # candidate here in every case).
    assert page.get_by_text("How were these numbers computed?").count() >= 1


@pytest.mark.parametrize(
    "engine,axis",
    [
        ("Monte Carlo", "state"),
        ("Monte Carlo", "roth_conversion_strategy"),
        ("Deterministic", "roth_conversion_strategy"),
        ("Monte Carlo", "withdrawal_sequencing"),
        ("Deterministic", "withdrawal_sequencing"),
        ("Monte Carlo", "claiming_age_grid"),
        ("Deterministic", "claiming_age_grid"),
    ],
)
def test_compare_runs_on_every_supported_engine_axis_combination(page, e2e_stack, engine, axis):
    _run_one_compare(page, e2e_stack, engine=engine, axis=axis)


def test_deterministic_engine_hides_the_state_axis(page, e2e_stack):
    """FR-010: state is never offered on Deterministic -- enforced
    client-side, confirmed here against the real rendered page."""
    page.goto(f"{e2e_stack.ui_base_url}/Compare", timeout=30_000)
    wait_for_ready(page)

    select_radio(page, "Deterministic")
    axis_combo = page.get_by_role("combobox", name="Axis", exact=True)
    axis_combo.click()
    axis_combo.press("ArrowDown")
    page.wait_for_timeout(300)
    options = [page.get_by_role("option").nth(i).inner_text() for i in range(page.get_by_role("option").count())]
    assert "state" not in options
