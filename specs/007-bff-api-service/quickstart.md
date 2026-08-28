# Quickstart: BFF API Service

Validates the feature end-to-end: save/read/list/validate/delete a scenario, discover reference data, run a simulation, run both kinds of comparison, and export to CSV — all through HTTP requests (via FastAPI's in-process `TestClient`, no real socket needed) — per SC-001–SC-008.

> **All dollar figures, ages, and rates below are illustrative placeholders**, exactly as `001`–`006`'s quickstarts note for their own placeholder figures. This feature introduces no new figures of its own — every unverified-figure indicator it surfaces originates from `002`/`003`/`005`.

## Prerequisites

- Python 3.11+, plus this feature's own dependencies (`pip install -e services/bff` from the repo root, or equivalent) — the only feature in this project so far with a runtime dependency beyond `pyyaml` (plan.md's Constitution Check).
- No network access needed once installed — `TestClient` runs the app in-process; a real deployment binds `127.0.0.1` only (research.md §1).

## 1. Save, read, list, validate, and delete a scenario (User Story 1)

```python
from fastapi.testclient import TestClient
from rp_bff.main import app

client = TestClient(app)

scenario_body = {
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
    "simulation_settings": {"n_paths": 5_000, "seed": 42, "plan_to_age": 95},
    "roth_conversion": {"strategy": "fill_to_bracket", "bracket_ceiling_or_amount": 206_700, "window": [2028, 2034]},
}

save_response = client.put("/api/v1/scenarios/base_case", json=scenario_body)
assert save_response.status_code == 200                                   # US1.1
assert save_response.json()["is_usable"] is True

list_response = client.get("/api/v1/scenarios")
assert "base_case" in list_response.json()["scenarios"]                   # US1.2

# A scenario with a validation problem is still saveable, but its blocking
# flag is reported, both on save and on validate-only (US1.3).
invalid_body = {**scenario_body, "accounts": [{"account_type": "traditional", "balance": -100}]}
validate_response = client.post("/api/v1/scenarios/base_case/validate", json=invalid_body)
assert any(flag["severity"] == "blocking" for flag in validate_response.json()["validation_flags"])

# Saving under the same name replaces, not merges (US1.4).
client.put("/api/v1/scenarios/base_case", json=scenario_body)
read_response = client.get("/api/v1/scenarios/base_case")
assert read_response.json()["accounts"] == scenario_body["accounts"]

# Delete, then confirm it's gone (US1.5-US1.6).
delete_response = client.delete("/api/v1/scenarios/base_case")
assert delete_response.status_code == 204
missing_response = client.get("/api/v1/scenarios/base_case")
assert missing_response.status_code == 404
assert missing_response.json()["error"] == "no_such_scenario"

# Re-save for the remaining steps.
client.put("/api/v1/scenarios/base_case", json=scenario_body)
```

**Expected outcome**: a scenario can be fully managed through HTTP alone — saved, read back identically, listed, validated (with or without saving), and removed, with a clear, distinguishable "no such scenario" response once it's gone.

## 2. Discover current reference data (User Story 2)

```python
states = client.get("/api/v1/reference/states").json()["states"]
assert states == sorted(states)                                            # US2.1
assert set(states).issubset({"SC", "DE", "FL"})                            # today's registered states only

withdrawal_strategies = client.get("/api/v1/reference/withdrawal-strategies").json()["withdrawal_strategies"]
conversion_strategies = client.get("/api/v1/reference/conversion-strategies").json()["conversion_strategies"]
axes = client.get("/api/v1/reference/comparison-axes").json()["axes"]
assert "state" in axes                                                     # US2.3
```

**Expected outcome**: every reference-data list matches its underlying `002`/`003`/`005` registry exactly, live — a state added to `002` in the future appears here automatically, with no change to this service (US2.2).

## 3. Run a simulation and receive a summary (User Story 3)

```python
run_body = {
    "scenario_name": "base_case",
    "reference_tax_year": 2026, "start_plan_year": 1, "start_tax_year": 2026,   # required, never defaulted (US3.4)
}

run_response = client.post("/api/v1/simulations", json=run_body)
assert run_response.status_code == 200
payload = run_response.json()
assert "run" in payload and "summary" in payload                           # US3.1
assert 0.0 <= payload["summary"]["success_rate"] <= 1.0

# Identical request twice -> identical results (US3.3).
repeat_response = client.post("/api/v1/simulations", json=run_body)
assert repeat_response.json() == payload
```

**Expected outcome**: one request returns both the full run and its `006`-computed summary; identical requests (including the scenario-derived default seed, since none was supplied) always produce identical results.

## 4. Run comparisons of both kinds (User Story 4)

```python
state_comparison_body = {
    **run_body,
    "axis": "state",
    "candidates": ["SC", "DE", "FL"],
}
state_comparison = client.post("/api/v1/comparisons/simulated", json=state_comparison_body)
assert len(state_comparison.json()["summaries"]) == 3                      # US4.1

deterministic_body = {
    **run_body,
    "axis": "roth_conversion_strategy",
    "candidates": [
        {"label": "no_conversion", "conversion_strategy": None, "conversion_bracket_ceiling_or_amount": None, "conversion_window": None},
    ],
}
deterministic_comparison = client.post("/api/v1/comparisons/deterministic", json=deterministic_body)
summaries = deterministic_comparison.json()["summaries"]
assert len(summaries) == 1                                                 # US4.4 -- one candidate is still valid
assert summaries[0]["success_rate"] is None                                # US4.2 -- not applicable, per 006

# An unrecognized axis/candidate value is rejected with a specific reason (US4.3).
bad_response = client.post("/api/v1/comparisons/simulated", json={**run_body, "axis": "state", "candidates": ["ZZ"]})
assert bad_response.status_code == 422
assert bad_response.json()["error"] == "unknown_reference_value"
```

**Expected outcome**: both comparison engines return one summarized result per candidate, in request order; a single-candidate comparison is still valid; an unrecognized reference value is rejected with a specific, actionable reason rather than silently ignored.

## 5. Export a run or comparison to CSV (User Story 5)

```python
run_csv = client.post("/api/v1/reports/simulations.csv", json=run_body)
assert run_csv.headers["content-type"].startswith("text/csv")
assert run_csv.text.splitlines()[0].startswith("plan_year")                # US5.1

comparison_csv = client.post(
    "/api/v1/reports/comparisons.csv?engine=simulated", json=state_comparison_body
)
assert all(state in comparison_csv.text for state in ("SC", "DE", "FL"))   # US5.2
assert "has_unverified_figure" in comparison_csv.text.splitlines()[0]      # US5.3
```

**Expected outcome**: the same request shape that returns a JSON run/comparison also returns a spreadsheet-ready CSV export when sent to the `/reports/*` endpoints, with `006`'s verification-status column intact.

## Running the automated version

Once implemented, the equivalent assertions above are `services/bff/tests/integration/test_bff_lifecycle.py`:

```bash
pytest services/bff/tests/integration/test_bff_lifecycle.py -v
```

All steps passing is the acceptance bar for this feature — see [contracts/bff-api.md](./contracts/bff-api.md) for the exact request/response shapes exercised above.
