# Quickstart: Year-by-Year Results Walkthrough

## Prerequisites

- Repo checked out on `028-results-walkthrough`, core deps installed.
- `pytest tests/` passing before starting (baseline for SC-005).

## 1. Select a representative path and build its narrative directly (US1, US2)

```python
from retirement_planner.reporting import build_narrative_for_run, select_representative_path
from retirement_planner.simulation import run_simulation

run = run_simulation(
    household=household,          # a Household with at least 2 plan years' horizon
    accounts=accounts,
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=40_000.0,
    state="FL",
    reference_tax_year=2026,
    start_plan_year=1,
    start_tax_year=2026,
    plan_to_age=90,
    strategy=strategy,
    return_paths=return_paths,     # >= 2 distinct ReturnPaths so paths actually differ
    candidate_label="quickstart",
)

index = select_representative_path(run)
assert 0 <= index < len(run.path_results)

narrative = build_narrative_for_run(run, household=household, reference_tax_year=2026)
assert narrative.selected_path_index == index
assert len(narrative.years) == len(run.path_results[index].years)          # FR-002: every plan year covered
assert all(story.entries for story in narrative.years)                      # FR-005: never empty
```

## 2. Confirm reproducibility (US2, FR-006/SC-002)

```python
run_again = run_simulation(..., candidate_label="quickstart")  # identical args, identical seed upstream
narrative_again = build_narrative_for_run(run_again, household=household, reference_tax_year=2026)

assert narrative.selected_path_index == narrative_again.selected_path_index
assert narrative.years == narrative_again.years  # dataclass equality -- byte-identical text too
```

## 3. Confirm a transition-only driver fires exactly once (US1)

```python
# In a fixture where RMDs start partway through the horizon (e.g., the deemed owner crosses 73):
rmd_years = [
    story.plan_year
    for story in narrative.years
    for entry in story.entries
    if entry.driver_key == "rmd_start"
]
assert len(rmd_years) == 1  # fires on the transition year only, never repeats (research.md §2)
```

## 4. Call it through the BFF (US1, US3)

```bash
curl -s -X POST http://localhost:8000/simulations \
  -H "Content-Type: application/json" \
  -d '{"scenario_name": "example", "reference_tax_year": 2026, "start_plan_year": 1, "start_tax_year": 2026}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['narrative']['selected_path_index'], len(d['narrative']['years']))"
```

Expected: the existing `run`/`summary`/`account_detail` keys are unchanged in shape, plus one new
`narrative` key shaped per [contracts/reporting-narrative-api.md](contracts/reporting-narrative-api.md).

## 5. Walk through it in the UI (US1, US3)

1. Start the BFF and Streamlit UI (see project run instructions).
2. Open **Run Simulation**, run any scenario.
3. Open the new **Walkthrough** page — it shows the first batch of up to 3 plan years of one
   representative path with plain-language stories, without triggering a new network request
   (same `run_last_result` session-state object).
4. Click **Next**/**Previous** to move through the projection; confirm the controls disable at
   the first/last batch (FR-010).
5. If any figure shown is flagged unverified elsewhere in the tool (e.g., an NC Bailey exclusion
   or a historical-bootstrap return), confirm the same warning appears here, scoped to the year
   it's used in (US3, FR-011).
6. Open the **Walkthrough** page with no prior run in this session — confirm it guides you to run
   a simulation first instead of erroring (FR-013).

## 6. Run the test suites

```bash
pytest tests/unit/reporting/test_narrative.py   # new: driver detection, path selection, reproducibility
pytest tests/                                    # core: confirm zero change to any other suite (SC-005)
pytest services/bff/tests/                       # BFF: new narrative field + all existing tests unchanged
pytest apps/streamlit_ui/tests/                  # UI: new Walkthrough page tests + all existing tests unchanged
```

## Expected outcome

Every plan year of the selected representative path has a non-empty, plain-language story paired
with its existing numeric detail (SC-001); re-running the same scenario+seed reproduces the exact
same selected path and narrative text (SC-002); every already-unverified figure stays visibly
flagged (SC-003); Next/Previous cover the full projection without erroring (SC-004); and all four
test suites pass with zero change to any other feature's output (SC-005).
