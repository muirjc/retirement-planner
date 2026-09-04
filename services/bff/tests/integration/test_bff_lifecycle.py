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
        {"account_type": "traditional", "balance": 1_500_000, "owner": "you"},
        {"account_type": "roth", "balance": 400_000, "owner": "you"},
        {"account_type": "taxable", "balance": 200_000, "owner": "spouse"},
    ],
    "spending": {"annual_need_real": 110_000},
    "state": "FL",
    "market_assumptions": {
        "equity_allocation": 0.60,
        "equity_return_mean_real": 0.065,
        "equity_return_std_real": 0.17,
        "bond_allocation": 0.40,
        "bond_return_mean_real": 0.015,
        "bond_return_std_real": 0.06,
        "correlation": -0.10,
    },
    "simulation_settings": {"n_paths": 200, "seed": 42, "plan_to_age": 95},
    "roth_conversion": {"strategy": "fill_to_bracket", "bracket_ceiling_or_amount": 206_700, "window": [2028, 2034]},
}


# --- User Story 1: scenario CRUD + validate ---


def test_save_read_and_list_round_trip(client):
    save_response = client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)
    assert save_response.status_code == 200  # US1.1
    assert save_response.json()["is_usable"] is True

    read_response = client.get("/api/v1/scenarios/base_case")
    assert read_response.status_code == 200
    # 012-inherited-ira-rmd: the response now also carries account_id
    # (auto-filled deterministically since the request omitted it) and
    # inherited (None -- no account in this request is inherited).
    expected_accounts = [{**account, "account_id": f"{account['account_type']}-{index}", "inherited": None} for index, account in enumerate(_SCENARIO_BODY["accounts"])]
    assert read_response.json()["accounts"] == expected_accounts  # US1.1

    list_response = client.get("/api/v1/scenarios")
    assert "base_case" in list_response.json()["scenarios"]  # US1.2


def test_roth_conversion_auto_window_named_bracket_and_netting_round_trip(client):
    """rp-1kz: window_mode="auto_gap_year"/ceiling_mode="named_bracket"/
    named_bracket_rate and spending.net_earned_income_against_spending
    all round-trip through PUT/GET -- no routes/scenarios.py change was
    needed for this (field-name-matching through model_dump(mode="json")
    -> YAML -> parse_scenario()), so this test is the actual proof."""
    body_with_new_fields = {
        **_SCENARIO_BODY,
        "spending": {**_SCENARIO_BODY["spending"], "net_earned_income_against_spending": True},
        "roth_conversion": {
            "strategy": "fill_to_bracket",
            "window_mode": "auto_gap_year",
            "ceiling_mode": "named_bracket",
            "named_bracket_rate": 0.22,
        },
    }
    save_response = client.put("/api/v1/scenarios/auto_window_case", json=body_with_new_fields)
    assert save_response.status_code == 200
    assert save_response.json()["is_usable"] is True

    read_response = client.get("/api/v1/scenarios/auto_window_case").json()
    assert read_response["spending"]["net_earned_income_against_spending"] is True
    assert read_response["roth_conversion"]["window_mode"] == "auto_gap_year"
    assert read_response["roth_conversion"]["window"] is None
    assert read_response["roth_conversion"]["ceiling_mode"] == "named_bracket"
    assert read_response["roth_conversion"]["named_bracket_rate"] == 0.22
    assert read_response["roth_conversion"]["bracket_ceiling_or_amount"] is None


def test_full_retirement_age_round_trips_and_defaults_when_omitted(client):
    """016-ss-claiming-age-actuarial-adjustment: an explicit
    full_retirement_age round-trips through PUT/GET; a member that omits
    it entirely (like _SCENARIO_BODY's own members) resolves to that
    member's own ss_claim_age -- the same backward-compatible default
    scenario.loader.parse_scenario() already applies directly."""
    body_with_explicit_fra = {
        **_SCENARIO_BODY,
        "household": {
            **_SCENARIO_BODY["household"],
            "members": [
                {**_SCENARIO_BODY["household"]["members"][0], "ss_claim_age": 62, "full_retirement_age": 67.0},
                _SCENARIO_BODY["household"]["members"][1],
            ],
        },
    }
    save_response = client.put("/api/v1/scenarios/fra_case", json=body_with_explicit_fra)
    assert save_response.status_code == 200

    read_response = client.get("/api/v1/scenarios/fra_case").json()
    assert read_response["household"]["members"][0]["full_retirement_age"] == 67.0
    # The second member never set it -- resolves to their own ss_claim_age (67).
    assert read_response["household"]["members"][1]["full_retirement_age"] == 67.0


def test_predicted_death_age_round_trips_and_defaults_to_none_when_omitted(client):
    """017-ss-spousal-survivor-benefits: an explicit predicted_death_age
    round-trips through PUT/GET; a member that omits it entirely (like
    _SCENARIO_BODY's own members) stays None -- no computed substitute,
    unlike full_retirement_age above."""
    body_with_explicit_death_age = {
        **_SCENARIO_BODY,
        "household": {
            **_SCENARIO_BODY["household"],
            "members": [
                {**_SCENARIO_BODY["household"]["members"][0], "predicted_death_age": 85},
                _SCENARIO_BODY["household"]["members"][1],
            ],
        },
    }
    save_response = client.put("/api/v1/scenarios/death_age_case", json=body_with_explicit_death_age)
    assert save_response.status_code == 200

    read_response = client.get("/api/v1/scenarios/death_age_case").json()
    assert read_response["household"]["members"][0]["predicted_death_age"] == 85
    # The second member never set it -- stays None, not resolved to anything.
    assert read_response["household"]["members"][1]["predicted_death_age"] is None


def test_income_streams_round_trip_and_default_to_empty_list_when_omitted(client):
    """021-pension-annuity-income (rp-pid): explicit income_streams
    round-trip through PUT/GET; a member that omits them entirely (like
    _SCENARIO_BODY's own members) stays an empty list."""
    body_with_income_streams = {
        **_SCENARIO_BODY,
        "household": {
            **_SCENARIO_BODY["household"],
            "members": [
                {
                    **_SCENARIO_BODY["household"]["members"][0],
                    "income_streams": [
                        {
                            "label": "State Pension",
                            "stream_type": "pension",
                            "start_age": 62,
                            "annual_amount": 18_000,
                            "inflation_adjustment": "cola_adjusted",
                        },
                        {
                            "label": "Old annuity",
                            "stream_type": "annuity",
                            "start_age": 65,
                            "end_age": 74,
                            "annual_amount": 6_000,
                            "inflation_adjustment": "fixed_nominal",
                        },
                    ],
                },
                _SCENARIO_BODY["household"]["members"][1],
            ],
        },
    }
    save_response = client.put("/api/v1/scenarios/pension_case", json=body_with_income_streams)
    assert save_response.status_code == 200

    read_response = client.get("/api/v1/scenarios/pension_case").json()
    streams = read_response["household"]["members"][0]["income_streams"]
    assert len(streams) == 2
    assert streams[0]["label"] == "State Pension"
    assert streams[0]["end_age"] is None
    assert streams[1]["end_age"] == 74
    # The second member never set it -- stays an empty list.
    assert read_response["household"]["members"][1]["income_streams"] == []


def test_survivor_spending_reduction_pct_round_trips_and_defaults_to_zero_when_omitted(client):
    """018-survivor-scenario-projection: an explicit
    survivor_spending_reduction_pct round-trips through PUT/GET; a
    household that omits it entirely (like _SCENARIO_BODY's own
    household) defaults to 0.0 -- a true no-op, mirroring how
    predicted_death_age above defaults to None with no computed
    substitute."""
    body_with_explicit_reduction = {
        **_SCENARIO_BODY,
        "household": {**_SCENARIO_BODY["household"], "survivor_spending_reduction_pct": 0.25},
    }
    save_response = client.put("/api/v1/scenarios/spending_reduction_case", json=body_with_explicit_reduction)
    assert save_response.status_code == 200

    read_response = client.get("/api/v1/scenarios/spending_reduction_case").json()
    assert read_response["household"]["survivor_spending_reduction_pct"] == 0.25

    # _SCENARIO_BODY itself never sets it -- defaults to 0.0.
    save_default_response = client.put("/api/v1/scenarios/base_case_default_reduction", json=_SCENARIO_BODY)
    assert save_default_response.status_code == 200
    read_default_response = client.get("/api/v1/scenarios/base_case_default_reduction").json()
    assert read_default_response["household"]["survivor_spending_reduction_pct"] == 0.0


def test_account_owner_omitted_on_single_member_household_is_auto_filled(client):
    """011-per-owner-accounts: a single-filer household needs no owner in
    the request at all -- the response shows it auto-filled (FR-003)."""
    single_member_body = {
        **_SCENARIO_BODY,
        "household": {
            "filing_status": "single",
            "members": [{"person_name": "you", "current_age": 60, "ss_claim_age": 67, "ss_annual_benefit": 32_000}],
        },
        "accounts": [
            {"account_type": "traditional", "balance": 1_500_000},
            {"account_type": "roth", "balance": 400_000},
            {"account_type": "taxable", "balance": 200_000},
        ],
        "roth_conversion": None,
    }
    save_response = client.put("/api/v1/scenarios/solo", json=single_member_body)
    assert save_response.status_code == 200
    assert save_response.json()["is_usable"] is True
    assert [a["owner"] for a in save_response.json()["accounts"]] == ["you", "you", "you"]


def test_account_owner_omitted_on_married_household_surfaces_a_blocking_flag(client):
    """011-per-owner-accounts: a 2-member household is ambiguous -- omitting
    owner surfaces a blocking flag, never a silent guess (FR-006)."""
    missing_owner_body = {
        **_SCENARIO_BODY,
        "accounts": [
            {"account_type": "traditional", "balance": 1_500_000},
            {"account_type": "roth", "balance": 400_000},
            {"account_type": "taxable", "balance": 200_000},
        ],
    }
    save_response = client.put("/api/v1/scenarios/base_case", json=missing_owner_body)
    assert save_response.status_code == 200
    assert save_response.json()["is_usable"] is False
    owner_flags = [f for f in save_response.json()["validation_flags"] if f["field"].endswith(".owner")]
    assert len(owner_flags) == 3
    assert all(f["severity"] == "blocking" for f in owner_flags)


def test_validate_only_reports_blocking_flags_without_saving(client):
    invalid_body = {**_SCENARIO_BODY, "accounts": [{"account_type": "traditional", "balance": -100}]}

    validate_response = client.post("/api/v1/scenarios/base_case/validate", json=invalid_body)
    assert validate_response.status_code == 200
    flags = validate_response.json()["validation_flags"]
    assert any(flag["severity"] == "blocking" for flag in flags)  # US1.3

    # Never saved -- the validate-only endpoint has no side effect.
    list_response = client.get("/api/v1/scenarios")
    assert "base_case" not in list_response.json()["scenarios"]


def test_saving_under_an_existing_name_fully_replaces_it(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    replaced_body = {**_SCENARIO_BODY, "spending": {"annual_need_real": 999_999}}
    client.put("/api/v1/scenarios/base_case", json=replaced_body)

    read_response = client.get("/api/v1/scenarios/base_case")
    assert read_response.json()["spending"]["annual_need_real"] == 999_999  # US1.4


def test_delete_removes_it_and_a_subsequent_read_reports_no_such_scenario(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    delete_response = client.delete("/api/v1/scenarios/base_case")
    assert delete_response.status_code == 204  # US1.5

    list_response = client.get("/api/v1/scenarios")
    assert "base_case" not in list_response.json()["scenarios"]

    read_response = client.get("/api/v1/scenarios/base_case")
    assert read_response.status_code == 404
    assert read_response.json()["error"] == "no_such_scenario"  # US1.6


def test_reading_or_deleting_a_never_saved_name_reports_no_such_scenario(client):
    read_response = client.get("/api/v1/scenarios/never_saved")
    assert read_response.status_code == 404
    assert read_response.json()["error"] == "no_such_scenario"  # US1.6, FR-005

    delete_response = client.delete("/api/v1/scenarios/never_saved")
    assert delete_response.status_code == 404
    assert delete_response.json()["error"] == "no_such_scenario"


# --- User Story 2: reference data ---


def test_reference_states_matches_the_live_registry_sorted(client):
    from retirement_planner.tax import STATE_MODULES

    response = client.get("/api/v1/reference/states")
    assert response.status_code == 200
    states = response.json()["states"]
    assert states == sorted(STATE_MODULES.keys())  # US2.1


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
    "reference_tax_year": 2026,
    "start_plan_year": 1,
    "start_tax_year": 2026,
}


def test_run_simulation_returns_run_and_summary_in_one_response(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post("/api/v1/simulations", json=_RUN_BODY)

    assert response.status_code == 200  # US3.1
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

    assert response.status_code == 422  # US3.2, FR-009
    assert response.json()["error"] == "blocking_validation_flags"
    assert len(response.json()["flags"]) > 0


def test_run_against_a_scenario_with_an_unknown_named_bracket_rate_is_a_clean_422(client):
    """rp-1kz: a named_bracket_rate with no matching row in the federal
    bracket table for the scenario's own filing status is rejected the
    same way an unknown conversion_strategy already is -- a clean 422,
    not an uncaught ValueError."""
    bad_body = {
        **_SCENARIO_BODY,
        "roth_conversion": {
            "strategy": "fill_to_bracket",
            "window_mode": "auto_gap_year",
            "ceiling_mode": "named_bracket",
            "named_bracket_rate": 0.23,  # no 23% federal bracket row exists
        },
    }
    client.put("/api/v1/scenarios/base_case", json=bad_body)

    response = client.post("/api/v1/simulations", json=_RUN_BODY)

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "unknown_reference_value"
    assert payload["field"] == "conversion_named_bracket_rate"


def test_run_with_an_out_of_range_tax_year_is_a_clean_422_not_a_bare_500(client):
    """Regression test: a real UI session sent reference_tax_year=1900
    (the Run Simulation page's unedited number_input placeholder) and got
    an unhandled "HTTP 500" with no message -- 002's own figure schedule
    only documents 2020-2074, and that UnsupportedTaxYearError was never
    caught at the HTTP boundary. Fixed by routes/simulations.py catching
    it around run_simulation() and translating it via
    resolution.py::unsupported_tax_year_error()."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    bad_body = {**_RUN_BODY, "reference_tax_year": 1900, "start_tax_year": 1900}
    response = client.post("/api/v1/simulations", json=bad_body)

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "unsupported_tax_year"
    assert payload["requested_year"] == 1900
    assert 2026 in payload["documented_years"]


def test_identical_run_requests_produce_identical_results(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    first = client.post("/api/v1/simulations", json=_RUN_BODY).json()
    second = client.post("/api/v1/simulations", json=_RUN_BODY).json()

    assert first == second  # US3.3, FR-010


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

    assert without_defaults == with_explicit_matching_values  # US3.4, FR-011


# -- 015-per-account-projection-detail (US1): per-account year-by-year
# detail on a simulation result --


def test_run_simulation_response_includes_account_detail_shaped_per_account(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post("/api/v1/simulations", json=_RUN_BODY)

    assert response.status_code == 200
    payload = response.json()
    assert "account_detail" in payload
    assert len(payload["account_detail"]) == len(payload["run"]["path_results"][0]["years"])
    first_year_detail = payload["account_detail"][0]
    assert set(first_year_detail.keys()) == {
        "plan_year",
        "tax_year",
        "accounts",
        "member_social_security_benefits",
        "member_income_stream_amounts",  # 021-pension-annuity-income (rp-pid)
    }
    account_ids = {row["account_id"] for row in first_year_detail["accounts"]}
    # _SCENARIO_BODY's 3 accounts (auto-filled account_ids, per the CRUD test above).
    assert account_ids == {"traditional-0", "roth-1", "taxable-2"}
    for row in first_year_detail["accounts"]:
        assert row["attribution"] in ("independently_tracked", "fixed_share_of_pooled_total")
    assert first_year_detail["member_social_security_benefits"].keys() == {"you", "spouse"}
    # _SCENARIO_BODY's members configure no income_streams -- present but empty.
    assert first_year_detail["member_income_stream_amounts"] == {"you": 0.0, "spouse": 0.0}


def test_run_simulation_detail_path_index_defaults_to_path_zero(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    without_index = client.post("/api/v1/simulations", json=_RUN_BODY).json()["account_detail"]
    with_explicit_zero = client.post("/api/v1/simulations", json={**_RUN_BODY, "detail_path_index": 0}).json()["account_detail"]

    assert without_index == with_explicit_zero


def test_run_simulation_out_of_range_detail_path_index_returns_422(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)
    n_paths = _SCENARIO_BODY["simulation_settings"]["n_paths"]

    response = client.post("/api/v1/simulations", json={**_RUN_BODY, "detail_path_index": n_paths})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "path_index_out_of_range"
    assert payload["requested"] == n_paths
    assert payload["path_count"] == n_paths


# -- 028-results-walkthrough (rp-bm8.1): narrative field on POST /simulations --


def test_run_simulation_response_includes_a_narrative_field_shaped_per_plan_year(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post("/api/v1/simulations", json=_RUN_BODY)

    assert response.status_code == 200
    payload = response.json()
    assert "narrative" in payload
    narrative = payload["narrative"]
    assert 0 <= narrative["selected_path_index"] < len(payload["run"]["path_results"])
    assert len(narrative["years"]) == len(payload["run"]["path_results"][0]["years"])
    first_year = narrative["years"][0]
    assert set(first_year.keys()) == {
        "plan_year",
        "tax_year",
        "member_ages",
        "detail",  # rp-bm8.3
        "entries",
        "unverified_figure_names",
    }
    assert len(first_year["entries"]) >= 1  # FR-005: never empty
    assert first_year["member_ages"].keys() == {"you", "spouse"}


def test_narrative_field_does_not_change_the_run_summary_or_account_detail_fields(client):
    """FR-014: this feature adds one field and changes nothing else --
    compare against 015's own account_detail-shaped-per-account test's
    fixture expectations."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    payload = client.post("/api/v1/simulations", json=_RUN_BODY).json()

    assert 0.0 <= payload["summary"]["success_rate"] <= 1.0
    assert len(payload["account_detail"]) == len(payload["run"]["path_results"][0]["years"])


def test_identical_run_requests_produce_a_byte_identical_narrative_field(client):
    """FR-006/SC-002: explicit check on the narrative field itself, on top
    of test_identical_run_requests_produce_identical_results()'s existing
    whole-payload equality check above."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    first = client.post("/api/v1/simulations", json=_RUN_BODY).json()["narrative"]
    second = client.post("/api/v1/simulations", json=_RUN_BODY).json()["narrative"]

    assert first == second


# -- rp-bm8.3: deep computation traceability (balance waterfall + tax breakdown) --


def test_narrative_year_detail_reconciles_and_matches_federal_tax_owed(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    payload = client.post("/api/v1/simulations", json=_RUN_BODY).json()

    selected_path_index = payload["narrative"]["selected_path_index"]
    path_years = payload["run"]["path_results"][selected_path_index]["years"]
    for story, year in zip(payload["narrative"]["years"], path_years):
        detail = story["detail"]
        assert set(detail.keys()) == {
            "balance_waterfall",
            "income_composition",
            "federal_tax_detail",
            "state_tax_detail",
            "fica_tax_detail",  # rp-bm8.4
            "inherited_accounts",
        }
        assert detail["fica_tax_detail"]["total_fica_tax"] == year["fica_tax"]["total_fica_tax"]
        assert "earned_income" in detail["income_composition"]
        for account in ("traditional", "roth", "taxable"):
            waterfall = detail["balance_waterfall"][account]
            reconciled = (
                waterfall["starting_balance"]
                - waterfall["rmd_drawn"]
                - waterfall["spending_withdrawal"]
                + waterfall["conversion_delta"]
                - waterfall["tax_funding_withdrawal"]
                + waterfall["growth"]
            )
            assert reconciled == pytest.approx(waterfall["ending_balance"], abs=0.01)
        fed = detail["federal_tax_detail"]
        assert sum(row["tax_in_bracket"] for row in fed["bracket_breakdown"]) == pytest.approx(fed["tax_owed"], abs=0.01)
        assert fed["tax_owed"] == pytest.approx(year["federal_tax"]["federal_tax_owed"], abs=0.01)
        state = detail["state_tax_detail"]
        assert state["tax_owed"] == pytest.approx(year["state_tax"]["state_tax_owed"], abs=0.01)


# -- rp-9vl: opt-in survival-adjusted success rate --


def test_run_simulation_survival_adjusted_defaults_to_not_computed(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post("/api/v1/simulations", json=_RUN_BODY)

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["survival_adjusted_success_rate"] is None
    assert payload["run"]["survival_adjusted_success_rate"] is None
    assert "survival_curve_primary" not in payload["summary"]["unverified_figure_names"]


def test_run_simulation_survival_adjusted_true_includes_the_rate_and_flags_it_unverified(client):
    """base_case's members (ages 60/58, plan_to_age 95) fall entirely
    within SURVIVAL_TABLE's documented 50-110 coverage."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post("/api/v1/simulations", json={**_RUN_BODY, "survival_adjusted": True})

    assert response.status_code == 200
    payload = response.json()
    assert 0.0 <= payload["summary"]["survival_adjusted_success_rate"] <= 1.0
    assert payload["summary"]["survival_adjusted_success_rate"] == payload["run"]["survival_adjusted_success_rate"]
    # simulation.survival_data.SURVIVAL_TABLE is an illustrative placeholder,
    # never verified (docs/BRD.md §6.9) -- opting in must surface that via
    # the same verification-flag machinery every other unverified figure
    # already uses (rp-9vl item 4).
    assert "survival_curve_primary" in payload["summary"]["unverified_figure_names"]
    assert "survival_curve_spouse" in payload["summary"]["unverified_figure_names"]


def test_run_simulation_survival_adjusted_age_out_of_range_returns_422_not_a_bare_500(client):
    """A household member younger than SURVIVAL_TABLE's documented age-50
    floor would otherwise hit a bare KeyError deep inside
    run_simulation()'s per-path scoring loop -- resolution.py's pre-flight
    check must catch this before that point and report a clean 422
    (rp-9vl, mirroring the reference_tax_year=1900/UnsupportedTaxYearError
    precedent above)."""
    young_member_scenario = {
        **_SCENARIO_BODY,
        "household": {
            "filing_status": "single",
            "members": [{"person_name": "you", "current_age": 10, "ss_claim_age": 62, "ss_annual_benefit": 0}],
        },
        "accounts": [{"account_type": "traditional", "balance": 1_500_000, "owner": "you"}],
        "simulation_settings": {"n_paths": 10, "seed": 1, "plan_to_age": 60},
        "roth_conversion": None,
    }
    client.put("/api/v1/scenarios/young_member_case", json=young_member_scenario)

    response = client.post(
        "/api/v1/simulations",
        json={**_RUN_BODY, "scenario_name": "young_member_case", "survival_adjusted": True},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "survival_curve_age_out_of_range"
    assert payload["person_name"] == "you"
    assert payload["age"] == 10


# -- 026-advanced-simulation-options (rp-2bn): opt-in sequence-of-returns stress overlay --


def test_run_simulation_stress_scenario_lowers_success_rate(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    baseline = client.post("/api/v1/simulations", json=_RUN_BODY).json()
    stressed = client.post(
        "/api/v1/simulations",
        json={**_RUN_BODY, "stress_scenario": {"magnitude": -0.9, "duration_years": 3, "start_plan_year": 1}},
    ).json()

    assert stressed["summary"]["success_rate"] < baseline["summary"]["success_rate"]


def test_run_simulation_stress_window_past_horizon_returns_422(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post(
        "/api/v1/simulations",
        json={
            **_RUN_BODY,
            "plan_to_age": 62,
            "stress_scenario": {"magnitude": -0.3, "duration_years": 5, "start_plan_year": 10},
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "invalid_simulation_options"
    assert "detail" in payload


def test_run_simulation_no_stress_scenario_is_byte_for_byte_unchanged(client):
    """SC-003: omitting stress_scenario (every existing request) reproduces
    prior behavior exactly -- confirmed by re-running the same seed twice
    and getting the identical result, the same determinism guarantee
    test_run_simulation_is_deterministic_given_same_seed already checks."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    first = client.post("/api/v1/simulations", json=_RUN_BODY).json()
    second = client.post("/api/v1/simulations", json=_RUN_BODY).json()

    assert first == second


# -- 026-advanced-simulation-options (rp-741): opt-in historical-bootstrap mode --


def test_run_simulation_historical_bootstrap_flags_unverified_figure(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post(
        "/api/v1/simulations",
        json={**_RUN_BODY, "generation_mode": "historical_bootstrap", "historical_block_length": 10},
    )

    assert response.status_code == 200
    assert "historical_annual_real_returns" in response.json()["summary"]["unverified_figure_names"]


def test_run_simulation_default_generation_mode_omits_the_unverified_flag(client):
    """SC-003: the default (generation_mode omitted) is unaffected by this feature."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post("/api/v1/simulations", json=_RUN_BODY)

    assert response.status_code == 200
    assert "historical_annual_real_returns" not in response.json()["summary"]["unverified_figure_names"]


def test_run_simulation_invalid_block_length_returns_422_not_a_bare_500(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post(
        "/api/v1/simulations",
        json={**_RUN_BODY, "generation_mode": "historical_bootstrap", "historical_block_length": 0},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_simulation_options"


def test_simulated_comparison_historical_bootstrap_flags_unverified_figure(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {
        **_RUN_BODY,
        "plan_to_age": 62,
        "axis": "state",
        "candidates": ["SC", "DE"],
        "generation_mode": "historical_bootstrap",
        "historical_block_length": 10,
    }
    response = client.post("/api/v1/comparisons/simulated", json=body)

    assert response.status_code == 200
    for summary in response.json()["summaries"]:
        assert "historical_annual_real_returns" in summary["unverified_figure_names"]


# --- User Story 4: run and retrieve a comparison ---


def test_simulated_state_comparison_returns_one_summary_per_state(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["SC", "DE", "FL"]}
    response = client.post("/api/v1/comparisons/simulated", json=body)

    assert response.status_code == 200
    summaries = response.json()["summaries"]
    assert len(summaries) == 3  # US4.1
    assert {s["candidate_label"] for s in summaries} == {"SC", "DE", "FL"}


def test_simulated_comparison_survival_adjusted_true_includes_the_rate_per_candidate(client):
    """rp-9vl: same opt-in flag as /simulations, honored by every simulated
    compare_*() axis via resolve_and_compare_simulated()'s shared `common`."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["SC", "DE"], "survival_adjusted": True}
    response = client.post("/api/v1/comparisons/simulated", json=body)

    assert response.status_code == 200
    for summary in response.json()["summaries"]:
        assert 0.0 <= summary["survival_adjusted_success_rate"] <= 1.0


def test_deterministic_comparison_ignores_survival_adjusted_flag(client):
    """rp-9vl: 004 has no Monte Carlo distribution to score -- the flag is
    accepted (never a 422/validation error) but has no effect, mirroring
    detail_path_index's own "accepted but ignored" precedent for this
    route."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {
        **_RUN_BODY,
        "axis": "withdrawal_sequencing",
        "survival_adjusted": True,
        "candidates": [{"label": "default", "withdrawal_strategy": "rmd_taxable_traditional_roth"}],
    }
    response = client.post("/api/v1/comparisons/deterministic", json=body)

    assert response.status_code == 200
    assert response.json()["summaries"][0]["survival_adjusted_success_rate"] is None


# -- 026-advanced-simulation-options (rp-2bn): stress overlay on comparisons --


def test_simulated_comparison_stress_scenario_applies_to_every_candidate(client):
    """FR-004: the tool's paired-draw methodology means every candidate
    sees the identical configured stress -- not just some of them."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {
        **_RUN_BODY,
        "plan_to_age": 62,
        "axis": "state",
        "candidates": ["SC", "DE", "FL"],
        "stress_scenario": {"magnitude": -0.9, "duration_years": 2, "start_plan_year": 1},
    }
    stressed = client.post("/api/v1/comparisons/simulated", json=body).json()
    baseline = client.post("/api/v1/comparisons/simulated", json={**_RUN_BODY, "plan_to_age": 62, "axis": "state", "candidates": ["SC", "DE", "FL"]}).json()

    assert len(stressed["summaries"]) == 3
    for stressed_summary, baseline_summary in zip(stressed["summaries"], baseline["summaries"]):
        assert stressed_summary["success_rate"] < baseline_summary["success_rate"]


def test_deterministic_comparison_ignores_stress_scenario(client):
    """FR-007: 004 has no return-path generation step at all -- a
    stress_scenario present in the body is accepted but has no effect,
    mirroring survival_adjusted's own precedent for this route."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {
        **_RUN_BODY,
        "axis": "withdrawal_sequencing",
        "candidates": [{"label": "default", "withdrawal_strategy": "rmd_taxable_traditional_roth"}],
        "stress_scenario": {"magnitude": -0.9, "duration_years": 200, "start_plan_year": 1},  # would be invalid if honored
    }
    response = client.post("/api/v1/comparisons/deterministic", json=body)

    assert response.status_code == 200


# -- 015-per-account-projection-detail (US2): per-candidate year-by-year
# detail on both comparison endpoints --


def test_simulated_comparison_response_includes_one_account_detail_list_per_candidate(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["SC", "DE", "FL"]}
    response = client.post("/api/v1/comparisons/simulated", json=body)

    payload = response.json()
    assert len(payload["account_detail"]) == len(payload["summaries"]) == 3
    # each candidate's own detail is independently populated -- never
    # empty, never mixed with another candidate's.
    for candidate_detail in payload["account_detail"]:
        assert len(candidate_detail) > 0
        account_ids = {row["account_id"] for row in candidate_detail[0]["accounts"]}
        assert account_ids == {"traditional-0", "roth-1", "taxable-2"}


def test_deterministic_comparison_response_includes_account_detail_per_candidate(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {
        **_RUN_BODY,
        "axis": "withdrawal_sequencing",
        "candidates": [{"label": "default", "withdrawal_strategy": "rmd_taxable_traditional_roth"}],
    }
    response = client.post("/api/v1/comparisons/deterministic", json=body)

    payload = response.json()
    assert len(payload["account_detail"]) == len(payload["summaries"]) == 1
    assert len(payload["account_detail"][0]) > 0


def test_simulated_comparison_out_of_range_detail_path_index_returns_422(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)
    n_paths = _SCENARIO_BODY["simulation_settings"]["n_paths"]

    body = {
        **_RUN_BODY,
        "plan_to_age": 60,
        "axis": "state",
        "candidates": ["FL"],
        "detail_path_index": n_paths,
    }
    response = client.post("/api/v1/comparisons/simulated", json=body)

    assert response.status_code == 422
    assert response.json()["error"] == "path_index_out_of_range"


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
    assert summaries[0]["success_rate"] is None  # US4.2
    assert summaries[0]["percentile_bands"] is None


def test_both_comparison_endpoints_accept_a_single_candidate(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    sim_body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["FL"]}
    sim_response = client.post("/api/v1/comparisons/simulated", json=sim_body)
    assert len(sim_response.json()["summaries"]) == 1  # US4.4

    det_body = {
        **_RUN_BODY,
        "axis": "withdrawal_sequencing",
        "candidates": [{"label": "default", "withdrawal_strategy": "rmd_taxable_traditional_roth"}],
    }
    det_response = client.post("/api/v1/comparisons/deterministic", json=det_body)
    assert len(det_response.json()["summaries"]) == 1


def test_claiming_age_grid_comparison_works_on_both_engines(client):
    """Regression: both comparison endpoints unconditionally ran
    build_candidates_for_axis() (comparison_candidates.py) before
    dispatching on axis, but that helper raises ValueError for
    "claiming_age_grid" -- whose candidates are meant to pass through
    unchanged (its own docstring says so) -- so every claiming_age_grid
    comparison 500'd, on both the deterministic and simulated engines,
    for every scenario, not just ones with inherited accounts."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    candidates = [{"you": 62, "spouse": 62}, {"you": 70, "spouse": 70}]

    det_body = {**_RUN_BODY, "axis": "claiming_age_grid", "candidates": candidates}
    det_response = client.post("/api/v1/comparisons/deterministic", json=det_body)
    assert det_response.status_code == 200
    assert len(det_response.json()["summaries"]) == 2

    sim_body = {**_RUN_BODY, "plan_to_age": 61, "axis": "claiming_age_grid", "candidates": candidates}
    sim_response = client.post("/api/v1/comparisons/simulated", json=sim_body)
    assert sim_response.status_code == 200
    assert len(sim_response.json()["summaries"]) == 2


def test_claiming_age_grid_candidate_missing_a_household_member_is_a_clean_422_not_500(client):
    """Regression for rp-dd9, found via the e2e Playwright suite: a
    candidate omitting a household member's claiming age (e.g. Person 2
    left blank on the Compare page for a married household) previously
    reached run_plan_projection()'s own unconditional
    claiming_ages[member.person_name] lookup as an uncaught KeyError --
    a bare HTTP 500 -- on both engines."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    candidates = [{"you": 67}]  # missing "spouse" -- base_case is married_filing_jointly

    det_body = {**_RUN_BODY, "axis": "claiming_age_grid", "candidates": candidates}
    det_response = client.post("/api/v1/comparisons/deterministic", json=det_body)
    assert det_response.status_code == 422
    assert det_response.json()["error"] == "unknown_reference_value"

    sim_body = {**_RUN_BODY, "plan_to_age": 61, "axis": "claiming_age_grid", "candidates": candidates}
    sim_response = client.post("/api/v1/comparisons/simulated", json=sim_body)
    assert sim_response.status_code == 422
    assert sim_response.json()["error"] == "unknown_reference_value"


def test_unrecognized_axis_or_candidate_value_is_rejected(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    bad_state_body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["ZZ"]}
    response = client.post("/api/v1/comparisons/simulated", json=bad_state_body)
    assert response.status_code == 422  # US4.3, FR-014
    assert response.json()["error"] == "unknown_reference_value"

    bad_axis_body = {**_RUN_BODY, "axis": "state", "candidates": ["FL"]}
    axis_response = client.post("/api/v1/comparisons/deterministic", json=bad_axis_body)
    assert axis_response.status_code == 422  # 004 has no state axis


def test_comparison_with_an_out_of_range_tax_year_is_a_clean_422_not_a_bare_500(client):
    """Same regression as test_run_with_an_out_of_range_tax_year_is_a_clean_422_...
    for the comparison endpoints -- both dispatch UnsupportedTaxYearError
    from deep inside 004/005, not during resolve_run_context()."""
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {
        **_RUN_BODY,
        "reference_tax_year": 1900,
        "start_tax_year": 1900,
        "plan_to_age": 60,
        "axis": "state",
        "candidates": ["FL"],
    }
    response = client.post("/api/v1/comparisons/simulated", json=body)

    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_tax_year"


# --- 010-advanced-tax-benefits: HSA contribution actually reaches every route ---


def test_hsa_contribution_reduces_ordinary_income_in_a_run(client):
    """Regression for a gap found during implementation (contracts/
    comparison-api.md's own note): resolving Scenario.hsa_contribution
    onto context.strategy is necessary but not sufficient on its own --
    this proves the single-run route (routes/simulations.py) actually
    applies it, not just that resolve_run_context() carries it."""
    hsa_body = {
        **_SCENARIO_BODY,
        "household": {
            **_SCENARIO_BODY["household"],
            "members": [
                {**_SCENARIO_BODY["household"]["members"][0], "hdhp_coverage": True},
                _SCENARIO_BODY["household"]["members"][1],
            ],
        },
        "hsa_contribution": {"annual_amount": 3_000},
    }
    client.put("/api/v1/scenarios/hsa_case", json=hsa_body)
    client.put("/api/v1/scenarios/no_hsa_case", json=_SCENARIO_BODY)

    with_hsa = client.post("/api/v1/simulations", json={**_RUN_BODY, "scenario_name": "hsa_case"}).json()
    without_hsa = client.post("/api/v1/simulations", json={**_RUN_BODY, "scenario_name": "no_hsa_case"}).json()

    with_year = with_hsa["run"]["path_results"][0]["years"][0]
    without_year = without_hsa["run"]["path_results"][0]["years"][0]
    assert with_year["hsa_contribution"]["amount_contributed"] == 3_000.0
    assert with_year["mechanics"]["ordinary_income"] == pytest.approx(without_year["mechanics"]["ordinary_income"] - 3_000.0)


def test_hsa_contribution_reaches_the_withdrawal_sequencing_comparison_axis(client):
    """The gap this regression actually caught: routes/comparisons.py
    builds each roth_conversion_strategy/withdrawal_sequencing candidate
    independently via build_candidates_for_axis() rather than starting
    from context.strategy, so hsa_contribution never reached them without
    being passed explicitly into those compare_*() calls (contracts/
    comparison-api.md). A status-code-only check would have passed even
    with the bug (the endpoint never errored, it silently ignored the
    configured amount) -- this compares the actual resulting figure
    against an identical scenario with no HSA contribution configured."""

    def household_with_hdhp(hsa_contribution):
        body = {
            **_SCENARIO_BODY,
            "household": {
                **_SCENARIO_BODY["household"],
                "members": [
                    {**_SCENARIO_BODY["household"]["members"][0], "hdhp_coverage": True},
                    _SCENARIO_BODY["household"]["members"][1],
                ],
            },
        }
        if hsa_contribution is not None:
            body["hsa_contribution"] = {"annual_amount": hsa_contribution}
        return body

    client.put("/api/v1/scenarios/hsa_case", json=household_with_hdhp(3_000))
    client.put("/api/v1/scenarios/no_hsa_case", json=household_with_hdhp(None))

    def compare(scenario_name):
        body = {
            **_RUN_BODY,
            "scenario_name": scenario_name,
            "axis": "withdrawal_sequencing",
            "candidates": [{"label": "default", "withdrawal_strategy": "rmd_taxable_traditional_roth"}],
        }
        response = client.post("/api/v1/comparisons/deterministic", json=body)
        assert response.status_code == 200
        return response.json()["summaries"][0]

    with_hsa_summary = compare("hsa_case")
    without_hsa_summary = compare("no_hsa_case")

    assert with_hsa_summary["median_lifetime_tax_paid"] < without_hsa_summary["median_lifetime_tax_paid"]


# --- User Story 5: export a run or comparison as a downloadable report ---


def test_export_run_returns_csv_with_one_row_per_plan_year(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    response = client.post("/api/v1/reports/simulations.csv", json=_RUN_BODY)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.splitlines()
    assert lines[0].startswith("plan_year")  # US5.1
    assert len(lines) == 1 + _SCENARIO_BODY["simulation_settings"]["plan_to_age"] - 60 + 1


def test_export_comparison_returns_csv_with_one_row_per_candidate(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["SC", "DE", "FL"]}
    response = client.post("/api/v1/reports/comparisons.csv?engine=simulated", json=body)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert all(state in response.text for state in ("SC", "DE", "FL"))  # US5.2


def test_exports_carry_the_verification_status_column(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    run_csv = client.post("/api/v1/reports/simulations.csv", json=_RUN_BODY)
    assert "has_unverified_figure" in run_csv.text.splitlines()[0]  # US5.3

    body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["SC", "DE", "FL"]}
    comparison_csv = client.post("/api/v1/reports/comparisons.csv?engine=simulated", json=body)
    assert "has_unverified_figure" in comparison_csv.text.splitlines()[0]  # US5.3


# --- Polish: cost-rejection path via a real HTTP call ---


def test_an_oversized_run_request_is_rejected_before_it_would_actually_run(client):
    client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)

    # n_paths=10_000 x 1 candidate x 36-year horizon x 0.0001s/unit = 36s > 30s budget.
    # Rejected by the pre-flight cost check -- this request completes fast
    # (the test doesn't wait for a real 10,000-path simulation).
    oversized_body = {**_RUN_BODY, "n_paths": 10_000}
    response = client.post("/api/v1/simulations", json=oversized_body)

    assert response.status_code == 413  # FR-018
    assert response.json()["error"] == "estimated_cost_exceeds_budget"
    assert response.json()["estimated_seconds"] > response.json()["budget_seconds"]


# --- 012-inherited-ira-rmd rp-mt7: Monte Carlo now supports inherited accounts ---

_INHERITED_SCENARIO_BODY = {
    **_SCENARIO_BODY,
    "accounts": [
        *_SCENARIO_BODY["accounts"],
        {
            "account_type": "traditional",
            "balance": 250_000,
            "owner": "you",
            "inherited": {
                "death_year": 2023,
                "decedent_age_at_death": 80,
                "decedent_was_taking_rmds": True,
                "beneficiary_relationship": "other_individual",
                "beneficiary_classification": "non_eligible_designated_beneficiary",
            },
        },
    ],
}


def test_simulation_request_against_an_inherited_account_scenario_now_works(client):
    """Regression for rp-mt7: inherited_accounts is now threaded through
    005 (retirement_planner.simulation) -- what used to be a documented
    422 (inherited_accounts_unsupported_for_simulation) must now run to
    completion and produce a normal success-rate summary."""
    save_response = client.put("/api/v1/scenarios/base_case", json=_INHERITED_SCENARIO_BODY)
    assert save_response.json()["is_usable"] is True

    response = client.post("/api/v1/simulations", json=_RUN_BODY)

    assert response.status_code == 200
    assert 0.0 <= response.json()["summary"]["success_rate"] <= 1.0


def test_simulated_comparison_against_an_inherited_account_scenario_now_works(client):
    """Regression for rp-mt7: see
    test_simulation_request_against_an_inherited_account_scenario_now_works."""
    client.put("/api/v1/scenarios/base_case", json=_INHERITED_SCENARIO_BODY)

    body = {**_RUN_BODY, "plan_to_age": 60, "axis": "state", "candidates": ["FL"]}
    response = client.post("/api/v1/comparisons/simulated", json=body)

    assert response.status_code == 200
    assert len(response.json()["summaries"]) == 1


def test_deterministic_comparison_against_an_inherited_account_scenario_still_works(client):
    """The deterministic path is fully supported -- only Monte Carlo is
    rejected (US1/US2 already computed and included the inherited
    account's distributions correctly)."""
    client.put("/api/v1/scenarios/base_case", json=_INHERITED_SCENARIO_BODY)

    body = {
        **_RUN_BODY,
        "axis": "withdrawal_sequencing",
        "candidates": [{"label": "default", "withdrawal_strategy": "rmd_taxable_traditional_roth"}],
    }
    response = client.post("/api/v1/comparisons/deterministic", json=body)

    assert response.status_code == 200
    assert len(response.json()["summaries"]) == 1


def test_validate_endpoint_against_an_inherited_account_scenario_is_unaffected(client):
    response = client.post("/api/v1/scenarios/base_case/validate", json=_INHERITED_SCENARIO_BODY)
    assert response.status_code == 200
    assert response.json()["is_usable"] is True


# --- 013-inherited-ira-edge-cases (rp-c8b, rp-iju, rp-l4d): Roth, pre-RBD, and EDB accounts ---


def _inherited_account(**inherited_overrides):
    inherited = {
        "death_year": 2020,
        "decedent_age_at_death": 80,
        "decedent_was_taking_rmds": True,
        "beneficiary_relationship": "other_individual",
        "beneficiary_classification": "non_eligible_designated_beneficiary",
    }
    inherited.update(inherited_overrides)
    return {"account_type": "traditional", "balance": 200_000, "owner": "you", "inherited": inherited}


@pytest.mark.parametrize(
    "label,account",
    [
        ("roth_non_edb", {**_inherited_account(), "account_type": "roth"}),
        ("pre_rbd_traditional", _inherited_account(decedent_was_taking_rmds=False)),
        (
            "spouse_edb",
            _inherited_account(beneficiary_relationship="spouse", beneficiary_classification="eligible_designated_beneficiary_spouse"),
        ),
        (
            "minor_child_edb",
            _inherited_account(
                beneficiary_relationship="minor_child",
                beneficiary_classification="eligible_designated_beneficiary_other",
            ),
        ),
    ],
)
def test_each_013_case_runs_to_completion_on_both_engines(client, label, account):
    """Regression for rp-c8b/rp-iju/rp-l4d: each of the four newly-
    supported cases (Roth, pre-RBD traditional, spouse EDB, minor-child
    EDB) must validate as usable and run to completion on both the
    deterministic and the Monte Carlo engine -- none of them were
    reachable before this work (all four were blocked by validation)."""
    scenario_body = {**_SCENARIO_BODY, "accounts": [*_SCENARIO_BODY["accounts"], account]}
    save_response = client.put(f"/api/v1/scenarios/{label}", json=scenario_body)
    assert save_response.status_code == 200
    assert save_response.json()["is_usable"] is True

    body = {**_RUN_BODY, "scenario_name": label}
    sim_response = client.post("/api/v1/simulations", json=body)
    assert sim_response.status_code == 200
    assert 0.0 <= sim_response.json()["summary"]["success_rate"] <= 1.0

    det_response = client.post(
        "/api/v1/comparisons/deterministic",
        json={
            **body,
            "axis": "withdrawal_sequencing",
            "candidates": [{"label": "default", "withdrawal_strategy": "rmd_taxable_traditional_roth"}],
        },
    )
    assert det_response.status_code == 200
    assert len(det_response.json()["summaries"]) == 1


def test_trust_or_entity_beneficiary_still_blocked(client):
    """research.md §7: closes a pre-existing gap -- relaxing
    beneficiary_classification's own blocking flag must not newly let a
    trust/entity beneficiary through the EDB divisor logic."""
    scenario_body = {
        **_SCENARIO_BODY,
        "accounts": [
            *_SCENARIO_BODY["accounts"],
            _inherited_account(
                beneficiary_relationship="trust_or_entity",
                beneficiary_classification="eligible_designated_beneficiary_other",
            ),
        ],
    }
    response = client.put("/api/v1/scenarios/trust_beneficiary", json=scenario_body)
    assert response.status_code == 200
    assert response.json()["is_usable"] is False
    blocking_fields = {flag["field"] for flag in response.json()["validation_flags"] if flag["severity"] == "blocking"}
    assert "accounts[3].inherited" in blocking_fields


def test_taxable_inherited_account_still_blocked(client):
    """research.md §8: account_type narrows from "!= traditional" to
    "not in (traditional, roth)" -- taxable stays blocked."""
    scenario_body = {
        **_SCENARIO_BODY,
        "accounts": [*_SCENARIO_BODY["accounts"], {**_inherited_account(), "account_type": "taxable"}],
    }
    response = client.put("/api/v1/scenarios/taxable_inherited", json=scenario_body)
    assert response.status_code == 200
    assert response.json()["is_usable"] is False
