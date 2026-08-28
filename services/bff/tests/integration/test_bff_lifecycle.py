"""Integration test: the full quickstart.md walkthrough for
007-bff-api-service (scenario CRUD+validate, reference data, simulation
runs, comparisons of both kinds, CSV export) — exercised via FastAPI's
TestClient, matching specs/007-bff-api-service/quickstart.md's five
sections.
"""

import pytest

_SCENARIO_BODY = {
    "household": {
        "filing_status": "married_filing_jointly",
        "members": [
            {"person_name": "you", "current_age": 60, "ss_claim_age": 67, "ss_annual_benefit": 32_000},
            {"person_name": "spouse", "current_age": 58, "ss_claim_age": 67, "ss_annual_benefit": 24_000},
        ],
    },
    "accounts": [
        {"account_type": "traditional", "balance": 1_500_000},
        {"account_type": "roth", "balance": 400_000},
        {"account_type": "taxable", "balance": 200_000},
    ],
    "spending": {"annual_need_real": 110_000},
    "state": "FL",
    "market_assumptions": {
        "equity_allocation": 0.60, "equity_return_mean_real": 0.065, "equity_return_std_real": 0.17,
        "bond_allocation": 0.40, "bond_return_mean_real": 0.015, "bond_return_std_real": 0.06,
        "correlation": -0.10,
    },
    "simulation_settings": {"n_paths": 200, "seed": 42, "plan_to_age": 95},
    "roth_conversion": {"strategy": "fill_to_bracket", "bracket_ceiling_or_amount": 206_700, "window": [2028, 2034]},
}


# --- User Story 1: scenario CRUD + validate ---


def test_save_read_and_list_round_trip(client):
    save_response = client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)
    assert save_response.status_code == 200                                       # US1.1
    assert save_response.json()["is_usable"] is True

    read_response = client.get("/api/v1/scenarios/base_case")
    assert read_response.status_code == 200
    assert read_response.json()["accounts"] == _SCENARIO_BODY["accounts"]         # US1.1

    list_response = client.get("/api/v1/scenarios")
    assert "base_case" in list_response.json()["scenarios"]                       # US1.2


def test_validate_only_reports_blocking_flags_without_saving(client):
    invalid_body = {**_SCENARIO_BODY, "accounts": [{"account_type": "traditional", "balance": -100}]}

    validate_response = client.post("/api/v1/scenarios/base_case/validate", json=invalid_body)
    assert validate_response.status_code == 200
    flags = validate_response.json()["validation_flags"]
    assert any(flag["severity"] == "blocking" for flag in flags)                  # US1.3

    # Never saved -- the validate-only endpoint has no side effect.
    list_response = client.get("/api/v1/scenarios")
    assert "base_case" not in list_response.json()["scenarios"]


def test_saving_under_an_existing_name_fully_replaces_it(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    replaced_body = {**_SCENARIO_BODY, "spending": {"annual_need_real": 999_999}}
    client.put("/api/v1/scenarios/base_case", json=replaced_body)

    read_response = client.get("/api/v1/scenarios/base_case")
    assert read_response.json()["spending"]["annual_need_real"] == 999_999        # US1.4


def test_delete_removes_it_and_a_subsequent_read_reports_no_such_scenario(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    delete_response = client.delete("/api/v1/scenarios/base_case")
    assert delete_response.status_code == 204                                     # US1.5

    list_response = client.get("/api/v1/scenarios")
    assert "base_case" not in list_response.json()["scenarios"]

    read_response = client.get("/api/v1/scenarios/base_case")
    assert read_response.status_code == 404
    assert read_response.json()["error"] == "no_such_scenario"                    # US1.6


def test_reading_or_deleting_a_never_saved_name_reports_no_such_scenario(client):
    read_response = client.get("/api/v1/scenarios/never_saved")
    assert read_response.status_code == 404
    assert read_response.json()["error"] == "no_such_scenario"                    # US1.6, FR-005

    delete_response = client.delete("/api/v1/scenarios/never_saved")
    assert delete_response.status_code == 404
    assert delete_response.json()["error"] == "no_such_scenario"


# --- User Story 2: reference data ---


def test_reference_states_matches_the_live_registry_sorted(client):
    from retirement_planner.tax import STATE_MODULES

    response = client.get("/api/v1/reference/states")
    assert response.status_code == 200
    states = response.json()["states"]
    assert states == sorted(STATE_MODULES.keys())                                 # US2.1


def test_reference_strategies_and_axes_match_their_registries(client):
    from retirement_planner.mechanics import CONVERSION_STRATEGIES, WITHDRAWAL_STRATEGIES

    withdrawal_response = client.get("/api/v1/reference/withdrawal-strategies")
    assert set(withdrawal_response.json()["withdrawal_strategies"]) == set(WITHDRAWAL_STRATEGIES.keys())  # US2.3

    conversion_response = client.get("/api/v1/reference/conversion-strategies")
    assert set(conversion_response.json()["conversion_strategies"]) == set(CONVERSION_STRATEGIES.keys())  # US2.3

    axes_response = client.get("/api/v1/reference/comparison-axes")
    axes = set(axes_response.json()["axes"])
    assert axes == {"state", "roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"}  # US2.3


# --- User Story 3: run a simulation and receive a summarized result ---

_RUN_BODY = {
    "scenario_name": "base_case",
    "reference_tax_year": 2026, "start_plan_year": 1, "start_tax_year": 2026,
}


def test_run_simulation_returns_run_and_summary_in_one_response(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post("/api/v1/simulations", json=_RUN_BODY)

    assert response.status_code == 200                                            # US3.1
    payload = response.json()
    assert "run" in payload and "summary" in payload
    assert 0.0 <= payload["summary"]["success_rate"] <= 1.0
    assert payload["summary"]["candidate_label"] is None
    assert len(payload["run"]["path_results"]) == _SCENARIO_BODY["simulation_settings"]["n_paths"]
    assert isinstance(payload["summary"]["unverified_figure_names"], list)


def test_run_against_a_scenario_with_blocking_flags_is_rejected_without_running(client):
    invalid_body = {**_SCENARIO_BODY, "accounts": [{"account_type": "traditional", "balance": -100}]}
    client.put("/api/v1/scenarios/base_case", json=invalid_body)

    response = client.post("/api/v1/simulations", json=_RUN_BODY)

    assert response.status_code == 422                                            # US3.2, FR-009
    assert response.json()["error"] == "blocking_validation_flags"
    assert len(response.json()["flags"]) > 0


def test_identical_run_requests_produce_identical_results(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    first = client.post("/api/v1/simulations", json=_RUN_BODY).json()
    second = client.post("/api/v1/simulations", json=_RUN_BODY).json()

    assert first == second                                                        # US3.3, FR-010


def test_omitted_seed_n_paths_plan_to_age_default_from_scenario_settings(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    without_defaults = client.post("/api/v1/simulations", json=_RUN_BODY).json()
    explicit_body = {
        **_RUN_BODY,
        "n_paths": _SCENARIO_BODY["simulation_settings"]["n_paths"],
        "seed": _SCENARIO_BODY["simulation_settings"]["seed"],
        "plan_to_age": _SCENARIO_BODY["simulation_settings"]["plan_to_age"],
    }
    with_explicit_matching_values = client.post("/api/v1/simulations", json=explicit_body).json()

    assert without_defaults == with_explicit_matching_values                       # US3.4, FR-011


# --- User Story 4: run and retrieve a comparison ---


def test_simulated_state_comparison_returns_one_summary_per_state(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["SC", "DE", "FL"]}
    response = client.post("/api/v1/comparisons/simulated", json=body)

    assert response.status_code == 200
    summaries = response.json()["summaries"]
    assert len(summaries) == 3                                                     # US4.1
    assert {s["candidate_label"] for s in summaries} == {"SC", "DE", "FL"}


def test_deterministic_roth_conversion_comparison_marks_monte_carlo_fields_not_applicable(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {
        **_RUN_BODY,
        "axis": "roth_conversion_strategy",
        "candidates": [
            {"label": "no_conversion", "conversion_strategy": None, "conversion_bracket_ceiling_or_amount": None, "conversion_window": None},
        ],
    }
    response = client.post("/api/v1/comparisons/deterministic", json=body)

    assert response.status_code == 200
    summaries = response.json()["summaries"]
    assert summaries[0]["success_rate"] is None                                    # US4.2
    assert summaries[0]["percentile_bands"] is None


def test_both_comparison_endpoints_accept_a_single_candidate(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    sim_body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["FL"]}
    sim_response = client.post("/api/v1/comparisons/simulated", json=sim_body)
    assert len(sim_response.json()["summaries"]) == 1                              # US4.4

    det_body = {
        **_RUN_BODY, "axis": "withdrawal_sequencing",
        "candidates": [{"label": "default", "withdrawal_strategy": "rmd_taxable_traditional_roth"}],
    }
    det_response = client.post("/api/v1/comparisons/deterministic", json=det_body)
    assert len(det_response.json()["summaries"]) == 1


def test_unrecognized_axis_or_candidate_value_is_rejected(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    bad_state_body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["ZZ"]}
    response = client.post("/api/v1/comparisons/simulated", json=bad_state_body)
    assert response.status_code == 422                                            # US4.3, FR-014
    assert response.json()["error"] == "unknown_reference_value"

    bad_axis_body = {**_RUN_BODY, "axis": "state", "candidates": ["FL"]}
    axis_response = client.post("/api/v1/comparisons/deterministic", json=bad_axis_body)
    assert axis_response.status_code == 422                                        # 004 has no state axis


# --- User Story 5: export a run or comparison as a downloadable report ---


def test_export_run_returns_csv_with_one_row_per_plan_year(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post("/api/v1/reports/simulations.csv", json=_RUN_BODY)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.splitlines()
    assert lines[0].startswith("plan_year")                                        # US5.1
    assert len(lines) == 1 + _SCENARIO_BODY["simulation_settings"]["plan_to_age"] - 60 + 1


def test_export_comparison_returns_csv_with_one_row_per_candidate(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["SC", "DE", "FL"]}
    response = client.post("/api/v1/reports/comparisons.csv?engine=simulated", json=body)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert all(state in response.text for state in ("SC", "DE", "FL"))             # US5.2


def test_exports_carry_the_verification_status_column(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    run_csv = client.post("/api/v1/reports/simulations.csv", json=_RUN_BODY)
    assert "has_unverified_figure" in run_csv.text.splitlines()[0]                 # US5.3

    body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["SC", "DE", "FL"]}
    comparison_csv = client.post("/api/v1/reports/comparisons.csv?engine=simulated", json=body)
    assert "has_unverified_figure" in comparison_csv.text.splitlines()[0]          # US5.3


# --- Polish: cost-rejection path via a real HTTP call ---


def test_an_oversized_run_request_is_rejected_before_it_would_actually_run(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    # n_paths=10_000 x 1 candidate x 36-year horizon x 0.0001s/unit = 36s > 30s budget.
    # Rejected by the pre-flight cost check -- this request completes fast
    # (the test doesn't wait for a real 10,000-path simulation).
    oversized_body = {**_RUN_BODY, "n_paths": 10_000}
    response = client.post("/api/v1/simulations", json=oversized_body)

    assert response.status_code == 413                                            # FR-018
    assert response.json()["error"] == "estimated_cost_exceeds_budget"
    assert response.json()["estimated_seconds"] > response.json()["budget_seconds"]
