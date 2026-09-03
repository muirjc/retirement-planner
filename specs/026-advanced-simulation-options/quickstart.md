# Quickstart: Advanced Simulation Options

## Prerequisites

- Repo checked out on `026-advanced-simulation-options`, core + BFF deps installed.
- `pytest services/bff/tests/` passing before starting (baseline for SC-003).

## 1. Run a stress-tested simulation (US1)

```python
client.put("/api/v1/scenarios/base_case", json=_SCENARIO_BODY)  # plan_to_age 95, current_age 60/58

baseline = client.post("/api/v1/simulations", json=_RUN_BODY).json()
stressed = client.post(
    "/api/v1/simulations",
    json={**_RUN_BODY, "stress_scenario": {"magnitude": -0.30, "duration_years": 3, "start_plan_year": 1}},
).json()

assert stressed["summary"]["success_rate"] < baseline["summary"]["success_rate"]
```

## 2. Reject a stress window past the horizon (US1 Acceptance Scenario 3)

```python
response = client.post(
    "/api/v1/simulations",
    json={**_RUN_BODY, "plan_to_age": 62, "stress_scenario": {"magnitude": -0.30, "duration_years": 5, "start_plan_year": 10}},
)
assert response.status_code == 422
assert response.json()["error"] == "invalid_simulation_options"
```

## 3. Run a historical-bootstrap simulation, flagged unverified (US2)

```python
result = client.post(
    "/api/v1/simulations",
    json={**_RUN_BODY, "generation_mode": "historical_bootstrap", "historical_block_length": 10},
).json()

assert "historical_annual_real_returns" in result["summary"]["unverified_figure_names"]
```

## 4. Reject an invalid block length

```python
response = client.post(
    "/api/v1/simulations",
    json={**_RUN_BODY, "generation_mode": "historical_bootstrap", "historical_block_length": 0},
)
assert response.status_code == 422
assert response.json()["error"] == "invalid_simulation_options"
```

## 5. Verify a comparison applies the same configuration to every candidate (FR-004)

```python
body = {
    **_RUN_BODY, "plan_to_age": 62, "axis": "state", "candidates": ["SC", "DE", "FL"],
    "stress_scenario": {"magnitude": -0.30, "duration_years": 2, "start_plan_year": 1},
}
result = client.post("/api/v1/comparisons/simulated", json=body).json()
assert len(result["summaries"]) == 3  # every candidate ran under the same stress
```

## 6. Verify the Deterministic engine is unaffected (FR-007)

```python
body = {**_RUN_BODY, "axis": "roth_conversion_strategy", "candidates": [...], "stress_scenario": {...}}
result = client.post("/api/v1/comparisons/deterministic", json=body).json()  # 200, unaffected
```

## 7. Verify a request touching neither option is byte-for-byte unchanged (SC-003)

Run any existing scenario fixture through `POST /simulations` and `POST /comparisons/simulated`
before and after this feature; every field must match exactly (both new fields default to
`generation_mode="parametric"`, `stress_scenario=None` — today's exact existing behavior).

## 8. Run the test suites

```bash
pytest services/bff/tests/       # routes + resolution.py
pytest apps/streamlit_ui/tests/  # page smoke coverage
```

## Expected outcome

- A household can configure and run a stress-tested simulation or comparison entirely from the Run
  Simulation / Compare pages' "Advanced overrides" expander, and see a measurably different result.
- A household can select historical-bootstrap mode and see the result clearly flagged as relying on
  an unverified data source, the same way every other unverified figure already is.
- A misconfigured stress window or block length produces a specific, actionable 422 error.
- Every existing request, and every existing saved scenario run without touching either option,
  produces output identical to its pre-feature result.
- The Deterministic comparison engine is completely unaffected.
