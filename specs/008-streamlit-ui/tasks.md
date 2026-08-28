---

description: "Task list for Streamlit UI"
---

# Tasks: Streamlit UI

**Input**: Design documents from `/specs/008-streamlit-ui/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/ui-pages.md](./contracts/ui-pages.md), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Project Structure specifies test files as deliverables, matching the precedent set by `001`–`007`. Testing uses `streamlit.testing.v1.AppTest` (Streamlit's own headless app-testing API) driving each page script directly, with `httpx.MockTransport` standing in for `007` so no real backend process is needed for the automated suite.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P5) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- File paths are exact and relative to the repository root

## Path Conventions

A third independently deployable package, `apps/streamlit_ui/`, sibling to `src/retirement_planner/` and `services/bff/` (plan.md's Structure Decision):
- New package code: `apps/streamlit_ui/{app.py,pages/,src/rp_ui/}`
- New package tests: `apps/streamlit_ui/tests/{unit,integration}/`

This is the **second** feature to add a runtime dependency beyond the core package's `pyyaml` — `streamlit`, `httpx`, `plotly` (plus Streamlit's own transitive dependencies), declared *only* in `apps/streamlit_ui/pyproject.toml`. This package depends on **neither** `retirement_planner` **nor** `rp_bff` (`007`'s package) — it talks to `007` exclusively over HTTP (research.md §1), enforced structurally by never declaring either as a dependency.

**Story dependency shape, different from every prior feature**: User Story 1 (Scenarios page) and the shared infrastructure it needs (Foundational) block everything else, since every later page needs a scenario to operate on. User Stories 2 and 3 (Run, Compare) are independent of each other once Foundational + US1 exist. User Stories 4 and 5 (verification indicator, CSV download) are **additive layers on top of the already-shipped US2/US3 pages** — small, explicit edits to `pages/2_Run_Simulation.py`/`pages/3_Compare.py`, not new pages of their own, mirroring the precedent `007`'s own US4/US5 set (later stories modifying earlier stories' files to add a capability, never reimplementing them). This is deliberate: none of US2's or US3's own Acceptance Scenarios mention the verification indicator or CSV download, so both pages are fully functional and independently testable *before* US4/US5 land.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the new package and confirm it installs correctly alongside `001`–`007` without disturbing them

- [X] T001 Create the `apps/streamlit_ui/` package skeleton: `apps/streamlit_ui/pyproject.toml` (deps: `streamlit`, `httpx`, `plotly`; dev deps: `pytest`), `apps/streamlit_ui/app.py` (stub), `apps/streamlit_ui/pages/__init__.py`-free `pages/` directory (Streamlit's own convention — no `__init__.py`, research.md §5), `apps/streamlit_ui/src/rp_ui/__init__.py`, `apps/streamlit_ui/tests/unit/__init__.py`, `apps/streamlit_ui/tests/integration/__init__.py` (plan.md Project Structure)
- [X] T002 Install `apps/streamlit_ui` in editable mode into the project's existing `.venv` (mirroring `007`'s own `uv pip install -e ... --python .venv/bin/python` fix for this environment's two-interpreter-tree quirk) and confirm `import rp_ui`, `import streamlit`, and `from streamlit.testing.v1 import AppTest` all succeed, and that `pytest tests/` (core) and `pytest services/bff/tests/` (`007`) both still pass unmodified (depends on T001)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The error-type vocabulary, the HTTP client every page calls, and the Home page every user lands on first

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Unit test every error type in `src/rp_ui/errors.py` (`ScenarioNotFoundError`, `InvalidScenarioError`, `BlockingValidationError`, `UnknownReferenceValueError`, `CostBudgetExceededError`, `BackendUnreachableError`, `UnexpectedBackendError`) carries the attributes data-model.md documents (research.md §4) in `apps/streamlit_ui/tests/unit/test_errors.py` — write FIRST, ensure it FAILS before T004
- [X] T004 Implement `src/rp_ui/errors.py` (research.md §4, data-model.md § Error types) (depends on T001, T003)
- [X] T005 [P] Unit test `src/rp_ui/api_client.py`'s shared request/response handling: each of `007`'s 5 documented error response shapes (404 `no_such_scenario`, 422 `invalid_scenario`, 422 `blocking_validation_flags`, 422 `unknown_reference_value`, 413 `estimated_cost_exceeds_budget`) raises the corresponding `errors.py` type, a connection failure raises `BackendUnreachableError`, an unrecognized non-2xx raises `UnexpectedBackendError`, and a 2xx response returns its parsed JSON body — all via `httpx.MockTransport` fixtures built from `007`'s actual documented response shapes (`specs/007-bff-api-service/contracts/bff-api.md`), not guessed shapes — write FIRST, ensure it FAILS before T006 in `apps/streamlit_ui/tests/unit/test_api_client.py`
- [X] T006 Implement `src/rp_ui/api_client.py` — `RP_BFF_BASE_URL` env var (default `http://127.0.0.1:8000/api/v1`, research.md §2), the shared `_request()` helper, and all 14 endpoint functions (data-model.md § API Client) (depends on T004, T005)
- [X] T007 [P] Unit test `app.py`'s Home page renders navigation and a live backend-status check, showing `BackendUnreachableError`'s message immediately if `list_states()` fails (contracts/ui-pages.md § `app.py`) in `apps/streamlit_ui/tests/integration/test_app_pages.py` — write FIRST, ensure it FAILS before T008
- [X] T008 Implement `apps/streamlit_ui/app.py` (depends on T006, T007)

**Checkpoint**: Foundation ready — User Story 1 implementation can now begin

---

## Phase 3: User Story 1 - Enter and manage a retirement scenario (Priority: P1) 🎯 MVP

**Goal**: A user can create, view, edit, save, and remove a named scenario through a form, with inline validation feedback and backend-driven selection options.

**Independent Test**: Fill in a new scenario's fields, save it, confirm it appears in a saved-scenario list, reopen and edit it, and remove it — without needing simulation, comparison, or export support to exist yet.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T013

- [X] T009 [P] [US1] `AppTest`-driven test: filling in a complete scenario and saving it results in it being read back with the same data and listed among saved scenarios (Acceptance Scenario US1.1) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T010 [US1] `AppTest`-driven test: a scenario with a blocking validation problem shows that problem inline, distinguishable from a warning-only flag, both on save and on validate-only (Acceptance Scenario US1.2) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T011 [US1] `AppTest`-driven test: the state/withdrawal-strategy/conversion-strategy selectors are populated only from `007`'s live reference-data responses, never a hardcoded option (Acceptance Scenario US1.3) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T012 [US1] `AppTest`-driven test: re-saving a scenario under an existing name fully replaces the previous data, and removing a scenario drops it from every list immediately (Acceptance Scenario US1.4) in `apps/streamlit_ui/tests/integration/test_app_pages.py`

### Implementation for User Story 1

- [X] T013 [US1] Implement `apps/streamlit_ui/pages/1_Scenarios.py` — the scenario form (household/accounts/spending/state/market-assumptions/simulation-settings/optional-Roth-conversion sections), Save/Validate/Load/Delete actions calling `api_client.py`'s scenario functions, inline `validation_flags` rendering distinguishing blocking from warning severity (contracts/ui-pages.md § `1_Scenarios.py`, FR-001–FR-005) (depends on T006, T008, T009–T012)

**Checkpoint**: User Story 1 is independently functional — quickstart.md §1 passes end-to-end. No run, comparison, verification indicator, or export support yet.

---

## Phase 4: User Story 2 - Run a simulation and see the results (Priority: P2)

**Goal**: A user can run a Monte Carlo simulation against a saved, valid scenario and see the success rate and a fan chart, with distinguishable error messages for every documented rejection reason.

**Independent Test**: Select one saved, valid scenario, run a simulation, and confirm a success rate and a percentile-band chart appear, matching the backend's response — without needing comparison, verification-indicator, or export support to exist yet.

### Tests for User Story 2 ⚠️

- [X] T014 [P] [US2] `AppTest`-driven test: running a simulation against a valid scenario displays the success rate and a fan chart matching the mocked `007` response's `summary` fields (Acceptance Scenario US2.1) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T015 [US2] `AppTest`-driven test: running against a scenario with a blocking flag shows the specific flags, distinct wording from a "scenario doesn't exist" message (Acceptance Scenario US2.2) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T016 [US2] `AppTest`-driven test: a `CostBudgetExceededError`-shaped mocked response shows the specific "too large" message, distinct from every other rejection reason (Acceptance Scenario US2.3) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T017 [US2] `AppTest`-driven test: a progress indicator is visible for the duration of a run request (Acceptance Scenario US2.4) in `apps/streamlit_ui/tests/integration/test_app_pages.py`

### Implementation for User Story 2

- [X] T018 [P] [US2] Implement `charts.fan_chart(percentile_bands)` in `src/rp_ui/charts.py` (data-model.md § Charts) (depends on T006)
- [X] T019 [US2] Implement `apps/streamlit_ui/pages/2_Run_Simulation.py` — scenario/withdrawal-strategy selection, `reference_tax_year`/`start_plan_year`/`start_tax_year` fields (always user-editable, never silently defaulted, research.md §2), an advanced-overrides expander, the Run action wrapped in `st.spinner()`, success-rate + fan-chart rendering, and per-error-type message rendering (contracts/ui-pages.md § `2_Run_Simulation.py`, FR-006–FR-008) (depends on T006, T018, T014–T017)

**Checkpoint**: User Stories 1–2 are functional — quickstart.md §1–2 pass end-to-end. No comparison, verification indicator, or export support yet.

---

## Phase 5: User Story 3 - Compare candidates and see the results overlaid (Priority: P3)

**Goal**: A user can compare two or more candidates on a chosen axis, using either engine, and see every candidate's outcome overlaid on one chart and summarized in one table.

**Independent Test**: Select a comparison axis and two or more candidates against one saved scenario, run the comparison, and confirm every candidate's outcome appears on one chart and in one table, in the order entered.

### Tests for User Story 3 ⚠️

- [X] T020 [P] [US3] `AppTest`-driven test: a Monte Carlo comparison across three state candidates displays a line-overlay chart (one line per candidate) and a summary table with one row per candidate, in request order (Acceptance Scenario US3.1) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T021 [US3] `AppTest`-driven test: selecting the deterministic engine removes `"state"` from the available axis choices (Acceptance Scenario US3.2) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T022 [US3] `AppTest`-driven test: a deterministic comparison's summary table shows `success_rate`/percentile-derived fields as "n/a", never a fabricated zero or blank, and renders `charts.comparison_bar_chart()` rather than an overlay (Acceptance Scenario US3.3, research.md §3) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T023 [US3] `AppTest`-driven test: a comparison with exactly one candidate still renders a valid chart and table (Acceptance Scenario US3.4) in `apps/streamlit_ui/tests/integration/test_app_pages.py`

### Implementation for User Story 3

- [X] T024 [P] [US3] Implement `charts.comparison_overlay_chart(summaries)` and `charts.comparison_bar_chart(summaries)` in `src/rp_ui/charts.py` — chart-shape selection reads each response's own `percentile_bands` (`null` vs. populated), never the engine selector alone (data-model.md § Charts, research.md §3) (depends on T006)
- [X] T025 [US3] Implement `apps/streamlit_ui/pages/3_Compare.py` — scenario/engine/axis selection (axis choices filtered by engine, FR-010), the axis-dependent candidate-list editor mirroring `007`'s own per-axis `candidates` shape, the Compare action, chart-shape dispatch, and the summary table (contracts/ui-pages.md § `3_Compare.py`, FR-009–FR-012) (depends on T006, T024, T020–T023)

**Checkpoint**: User Stories 1–3 are functional — quickstart.md §1–3 pass end-to-end. No verification indicator or export support yet.

---

## Phase 6: User Story 4 - See unverified figures flagged, wherever they appear (Priority: P4)

**Goal**: Every displayed run or comparison result visibly indicates whether an unverified figure informed it — an additive layer on the already-shipped Run and Compare pages, not a new page.

**Independent Test**: Run a simulation or comparison known to involve at least one unverified figure and confirm a visible indicator appears; confirm a result with none shows a positive "all verified" confirmation instead.

### Tests for User Story 4 ⚠️

- [X] T026 [P] [US4] Unit test `verification.render_verification_indicator()` renders a positive confirmation for an empty `unverified_figure_names` list and names every entry for a non-empty one (Acceptance Scenarios US4.1–US4.2) in `apps/streamlit_ui/tests/unit/test_verification.py`
- [X] T027 [US4] `AppTest`-driven test: the Run page shows the verification indicator after a successful run, reflecting the mocked response's `unverified_figure_names` (Acceptance Scenario US4.1) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T028 [US4] `AppTest`-driven test: the Compare page shows the verification indicator for each candidate (or the union across candidates) after a successful comparison (Acceptance Scenario US4.2) in `apps/streamlit_ui/tests/integration/test_app_pages.py`

### Implementation for User Story 4

- [X] T029 [US4] Implement `render_verification_indicator(unverified_figure_names)` in `src/rp_ui/verification.py` (data-model.md § Verification Indicator, FR-013) (depends on T006, T026)
- [X] T030 [US4] Integrate the verification indicator into `apps/streamlit_ui/pages/2_Run_Simulation.py` (depends on T019, T029, T027)
- [X] T031 [US4] Integrate the verification indicator into `apps/streamlit_ui/pages/3_Compare.py` (depends on T025, T029, T028)

**Checkpoint**: User Stories 1–4 are functional — quickstart.md §1–4 pass end-to-end. No export support yet.

---

## Phase 7: User Story 5 - Download a spreadsheet-ready report (Priority: P5)

**Goal**: A user viewing a run's or comparison's results can download the same results as a file — an additive layer on the already-shipped Run and Compare pages, not a new page.

**Independent Test**: View a run's or comparison's results and download a report of them, confirming the downloaded content matches what's on screen.

### Tests for User Story 5 ⚠️

- [X] T032 [P] [US5] `AppTest`-driven test: the Run page's download action calls `export_simulation_csv()` with the identical request body already used for the on-screen run, and the returned CSV text matches the mocked response (Acceptance Scenario US5.1) in `apps/streamlit_ui/tests/integration/test_app_pages.py`
- [X] T033 [US5] `AppTest`-driven test: the Compare page's download action calls `export_comparison_csv()` with the identical request body and engine, and the returned CSV text has one row per candidate matching the summary table (Acceptance Scenario US5.2) in `apps/streamlit_ui/tests/integration/test_app_pages.py`

### Implementation for User Story 5

- [X] T034 [US5] Wire a *Download CSV* action into `apps/streamlit_ui/pages/2_Run_Simulation.py` using `api_client.export_simulation_csv()` (already implemented in T006) (FR-014) (depends on T019, T032)
- [X] T035 [US5] Wire a *Download CSV* action into `apps/streamlit_ui/pages/3_Compare.py` using `api_client.export_comparison_csv()` (already implemented in T006) (FR-014) (depends on T025, T033)

**Checkpoint**: All five user stories are independently functional — scenario management, simulation runs, comparisons, verification flagging, and CSV export, per [quickstart.md](./quickstart.md) steps 1–5.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify this feature's cross-cutting requirements (dependency containment, a real end-to-end launch) and tie the quickstart walkthrough together as one acceptance run

- [X] T036 Run the complete [quickstart.md](./quickstart.md) walkthrough (all 5 sections) as one end-to-end assertion sequence in `apps/streamlit_ui/tests/integration/test_app_pages.py` (depends on T009–T012, T014–T017, T020–T023, T027–T028, T032–T033)
- [X] T037 [P] Confirm `apps/streamlit_ui/pyproject.toml` declares no dependency on `retirement_planner` or `rp_bff`, and that the repository-root `pyproject.toml` and `services/bff/pyproject.toml` both remain unchanged after this feature — a permanent pytest check (mirroring `007`'s own `test_dependency_containment.py`) asserting the Constitution Check's containment-boundary claim empirically (depends on T001)
- [X] T038 [P] Add docstrings to every public function/page script in `src/rp_ui/{api_client,errors,charts,verification}.py`, `app.py`, and each `pages/*.py`, referencing the corresponding section of [contracts/ui-pages.md](./contracts/ui-pages.md) (depends on T013, T019, T025, T030, T031, T034, T035)
- [X] T039 A real, one-time end-to-end launch: start a real `007` instance (`uvicorn rp_bff.main:app`, from `services/bff/`) and this app together (`streamlit run apps/streamlit_ui/app.py --server.headless true`), and confirm the Home page's live backend-status check succeeds against the actual running stack — not only the mocked `AppTest` suite (quickstart.md's manual-walkthrough prerequisite) (depends on T008)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational **and** User Story 1 conceptually (a scenario must exist to run against) — its own tasks don't literally touch `1_Scenarios.py`, but its `AppTest` fixtures assume a saved scenario exists, the same precondition every quickstart.md step after §1 shares
- **User Story 3 (Phase 5)**: Same relationship to User Story 1 as User Story 2 — independent of User Story 2 itself
- **User Story 4 (Phase 6)**: Depends on User Story 2's (`T019`) and User Story 3's (`T025`) page files existing, since it edits both
- **User Story 5 (Phase 7)**: Same dependency shape as User Story 4 — edits both already-shipped pages
- **Polish (Phase 8)**: `T036` depends on every story's integration tests; `T037` depends on T001; `T038`/`T039` depend on every story's implementation

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — the MVP slice
- **User Story 2 (P2)**: Depends on Foundational; conceptually needs a scenario to exist (User Story 1) for its own tests' fixtures, but adds no code to `1_Scenarios.py`
- **User Story 3 (P3)**: Same relationship as User Story 2 — independent of User Story 2 itself; **User Story 2 and User Story 3 can be built in parallel** once Foundational (and, for realistic fixtures, User Story 1) exist
- **User Story 4 (P4)**: Depends on both User Story 2 and User Story 3 (it edits both their files) — cannot start until both are merged
- **User Story 5 (P5)**: Same dependency shape as User Story 4 — **User Story 4 and User Story 5 can be built in parallel** once User Stories 2–3 exist, since they touch the same two files but add independent capabilities (verification indicator vs. download button) that don't conflict in intent, only in file-merge order

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task
- Foundational's `errors.py` (T004) before `api_client.py` (T006), which every page depends on
- Within User Story 2: `charts.fan_chart()` (T018) before the page that calls it (T019)
- Within User Story 3: both chart functions (T024) before the page that dispatches between them (T025)
- Within User Story 4: `verification.py` (T029) before its integration into either page (T030, T031)
- Within User Story 5: no new shared module — both page edits (T034, T035) only need `api_client.py`'s already-built export functions (T006)

### Parallel Opportunities

- T003 (`test_errors.py`) and T005 (`test_api_client.py`, once `errors.py` exists) target different files and can proceed in parallel with T007 (`test_app_pages.py`'s Home-page test) once Setup is done
- **User Story 2 and User Story 3 can be built fully in parallel** by different contributors once Foundational (and a realistic saved-scenario fixture) exists — neither depends on the other
- **User Story 4 and User Story 5 can be built in parallel** once User Stories 2–3 are merged — both edit `2_Run_Simulation.py`/`3_Compare.py`, but add independent capabilities (coordinate on merge order within those two files, same caveat `007`'s own parallel-example note carried)
- T037/T038/T039 in Polish can run in parallel — three independent verification concerns

---

## Parallel Example: User Story 2 and User Story 3

```bash
# Launch both stories' first tests together, once Foundational + a saved-scenario
# fixture exist (different sections of the same eventual test file --
# coordinate on merge order, or split into per-story test files if true
# concurrent authorship is needed):
Task: "AppTest-driven test: valid run displays success rate + fan chart"
Task: "AppTest-driven test: Monte Carlo comparison displays overlay chart + table"

# Launch both stories' page implementations together (different files):
Task: "Implement apps/streamlit_ui/pages/2_Run_Simulation.py"
Task: "Implement apps/streamlit_ui/pages/3_Compare.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest apps/streamlit_ui/tests/` and confirm SC-001 holds via quickstart.md §1
5. This alone proves the HTTP-client/error-handling foundation and the first real, human-usable screen — everything else layers on top of it

### Incremental Delivery

1. Setup + Foundational → foundation ready (error types, HTTP client, Home page live)
2. Add User Story 1 → scenario management → validate independently (SC-001) → this is the MVP
3. Add User Story 2 (and, in parallel, User Story 3) → run + compare, with charts → validate independently (SC-002, SC-003)
4. Add User Story 4 → verification indicator on both pages → validate independently (SC-004)
5. Add User Story 5 (in parallel with User Story 4 if staffed) → CSV download on both pages → validate independently (SC-005)
6. Polish → full quickstart.md walkthrough, dependency containment check, docstrings, one real end-to-end launch against a running `007` (SC-006)

### Suggested Team Split

User Story 1 must land first (the MVP, and the precondition every later story's test fixtures assume). Once it's merged: User Story 2 and User Story 3 can be split across two contributors immediately, since neither depends on the other. Once both are merged: User Story 4 and User Story 5 can likewise be split across two contributors — both touch the same two page files, so coordinate on merge order (the same caveat `007`'s own two-contributor examples already established for this project).
