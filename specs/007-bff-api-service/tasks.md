---

description: "Task list for BFF API Service"
---

# Tasks: BFF API Service

**Input**: Design documents from `/specs/007-bff-api-service/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/bff-api.md](./contracts/bff-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Project Structure and the constitution's Development Workflow gate ("unit test coverage for numeric primitives") both specify test files as deliverables of this feature, matching the precedent set by `001`–`006`.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P5) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- File paths are exact and relative to the repository root

## Path Conventions

A new, independently deployable package, `services/bff/`, sibling to the core `src/retirement_planner/` package (plan.md's Structure Decision — confirmed multi-package monorepo layout, not a subpackage or optional extra):
- New package code: `services/bff/src/rp_bff/`
- New package tests: `services/bff/tests/unit/`, `services/bff/tests/integration/`
- The one change inside the core package: `src/retirement_planner/scenario/{store,__init__}.py` (`delete_scenario()`, research.md §1)
- The one change to the core package's own tests: `tests/unit/scenario/test_store.py`

This is the first feature to add a runtime dependency beyond `pyyaml` — `fastapi`, `uvicorn[standard]`, `pydantic` (transitive), declared *only* in `services/bff/pyproject.toml`; the repository-root `pyproject.toml` (core package) is untouched (plan.md Constitution Check, Complexity Tracking). `httpx` is a test-only dependency of `services/bff` (required by FastAPI's `TestClient`).

**This feature's stories build on each other more than any prior feature**: User Story 1 (scenario CRUD) is the hard prerequisite for everything else — no run, comparison, or export request can resolve a scenario without it. User Story 3 (run a simulation) introduces the shared request-resolution logic (scenario lookup, `StrategyConfiguration` construction, blocking-flag check, reference-value validation, cost estimate) that User Story 4 (comparison) and User Story 5 (export) both reuse directly — mirroring how `006`'s `summarize_run()` became the base every later function in that feature reused. User Story 2 (reference data) is independent of everything except Foundational, and can be built in parallel with User Story 1.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the new, independently deployable package and confirm it installs and imports correctly in this environment

- [X] T001 Create the `services/bff/` package skeleton: `services/bff/pyproject.toml` (deps: `retirement_planner` as an editable path dependency, `fastapi`, `uvicorn[standard]`; dev deps: `httpx`, `pytest`), `services/bff/src/rp_bff/__init__.py`, `services/bff/src/rp_bff/routes/__init__.py`, `services/bff/tests/unit/__init__.py`, `services/bff/tests/integration/__init__.py` (plan.md Project Structure)
- [X] T002 Install `services/bff` in editable mode into the project's existing `.venv` and confirm `import rp_bff` succeeds and the core `retirement_planner` package remains importable and its own test suite (`pytest tests/`) still passes unmodified (189/189) — **finding**: this `.venv` has two interpreter trees (`python3.12` and `python3.14`); `.venv/bin/pip` is bound to 3.12, but `.venv/bin/python`/`python3` resolve to 3.14, and `retirement_planner`'s own editable install (already present) lives only in the 3.14 tree, installed originally via `uv` (evidenced by `uv_build.json`/`uv_cache.json` in its `dist-info`), not `pip`. `pip install -e services/bff[dev]` silently installed into the *wrong* (3.12) tree, invisible to the actual interpreter in use. Fixed via `uv pip install -e "services/bff[dev]" --python .venv/bin/python`, matching the tool that set up the rest of this environment (depends on T001)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `001` prerequisite (`delete_scenario()`), the JSON serializer, the cost estimator, the base FastAPI app, and the base request schemas every user story needs

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Unit test `delete_scenario()` removes a saved scenario's file and raises the same `ScenarioParseError` shape `load_scenario()` already raises for a name that was never saved (research.md §1) in `tests/unit/scenario/test_store.py` — write FIRST, ensure it FAILS before T004
- [X] T004 Implement `delete_scenario(name, *, scenarios_dir=None)` in `src/retirement_planner/scenario/store.py`, export from `src/retirement_planner/scenario/__init__.py` (FR-004, research.md §1) (depends on T003)
- [X] T005 [P] Unit test `to_jsonable()` converts `date` fields to ISO 8601 strings, `dict[float, float]` (e.g. `PercentileBand.percentiles`) to `[{"percentile": k, "value": v}, ...]`, `tuple` fields to JSON arrays, and recurses correctly through a nested dataclass (research.md §3) in `services/bff/tests/unit/test_serialization.py` — write FIRST, ensure it FAILS before T006
- [X] T006 Implement `to_jsonable()` in `services/bff/src/rp_bff/serialization.py` (research.md §3) (depends on T001, T005)
- [X] T007 [P] Unit test `estimate_cost_seconds()` against hand-computed reference cases (a request just under the 30-second rejection threshold, one just over it) (research.md §5) in `services/bff/tests/unit/test_cost_estimation.py` — write FIRST, ensure it FAILS before T008. **Finding during this task**: the original research.md draft's `PER_UNIT_COST_SECONDS` (1ms/unit) was based on misreading `005`'s benchmark ("~0.375ms per full 36-year projection" misread as "per path-year," a 36x error) — at that rate the reference-scale single run (US3.1/SC-003) would have been *incorrectly rejected* by this feature's own gate. Caught by writing `test_reference_scale_single_run_stays_within_budget` and recomputing against `006`'s actual measured 3.77s benchmark before adopting a value; corrected to `0.0001` (0.1ms/unit) and research.md §5 updated with the corrected math
- [X] T008 Implement `estimate_cost_seconds()` and the rejection check in `services/bff/src/rp_bff/cost_estimation.py` (FR-018, research.md §5 — corrected `PER_UNIT_COST_SECONDS = 0.0001`) (depends on T001, T007)
- [X] T009 [P] Wire the base FastAPI app in `services/bff/src/rp_bff/main.py` — app construction and a route-registration point, no routes registered yet (depends on T001)
- [X] T010 [P] Define the base `ScenarioRequest` Pydantic model tree (mirroring `001`'s `Scenario`/`Household`/`HouseholdMember`/`Account`/`SpendingProfile`/`MarketAssumptions`/`SimulationSettings`/`RothConversionPlan` fields exactly, minus `name` — supplied via the URL path and `parse_scenario(yaml_text, name=...)` instead, per `001`'s own `name or data.get("name")` override behavior, confirmed by reading `loader.py`) in `services/bff/src/rp_bff/schemas.py` (data-model.md § Scenario Resource) (depends on T001)

**Checkpoint**: Foundation ready — User Story 1 (and, independently, User Story 2) implementation can now begin

---

## Phase 3: User Story 1 - Save, load, and validate a scenario over HTTP (Priority: P1) 🎯 MVP

**Goal**: A client can `PUT`/`GET`/list/validate/`DELETE` a named scenario entirely through HTTP, with every operation matching `001`'s own function behavior exactly.

**Independent Test**: `PUT` a scenario, then separately `GET` it, list it among saved scenarios, and validate it, confirming each response matches calling `001`'s functions directly for the same data — without needing simulation, comparison, or export support to exist yet.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T016

- [X] T011 [P] [US1] Integration test: `PUT /scenarios/{name}` then `GET /scenarios/{name}` returns the same household/account/spending/state/market-assumption/simulation-setting data back, and `GET /scenarios` lists the name (Acceptance Scenarios US1.1–US1.2) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T012 [US1] Integration test: `POST /scenarios/{name}/validate` reports a blocking flag for an invalid scenario, both when submitted for validation only and when saved (Acceptance Scenario US1.3) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T013 [US1] Integration test: `PUT`-ing a scenario under an existing name fully replaces the previous data, matching `001`'s documented overwrite behavior (Acceptance Scenario US1.4) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T014 [US1] Integration test: `DELETE /scenarios/{name}` removes it from `GET /scenarios`'s list and a subsequent `GET /scenarios/{name}` returns a 404 with `error: "no_such_scenario"` (Acceptance Scenario US1.5) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T015 [US1] Integration test: `GET`/`DELETE` on a name that was never saved returns the same distinct `"no_such_scenario"` error shape as a deleted one (Acceptance Scenario US1.6, FR-005) in `services/bff/tests/integration/test_bff_lifecycle.py`

### Implementation for User Story 1

- [X] T016 [US1] Implement `PUT /scenarios/{name}`, `GET /scenarios/{name}`, `GET /scenarios`, `DELETE /scenarios/{name}`, `POST /scenarios/{name}/validate` in `services/bff/src/rp_bff/routes/scenarios.py` — converts the request's `ScenarioRequest` body to YAML text and calls `001`'s `parse_scenario()`/`save_scenario()`/`load_scenario()`/`list_scenarios()`/`delete_scenario()`/`validate()` unchanged, rendering responses through `to_jsonable()` (FR-001–FR-005, research.md §1, §3) (depends on T004, T006, T010, T011–T015). **Two findings**: (1) `Scenario.is_usable` is a `@property`, not a dataclass field, so `to_jsonable()`'s field-based recursion can't see it — fixed with a small explicit `_scenario_to_response()` merge rather than generalizing the serializer to guess at properties on every dataclass; (2) FastAPI's default `HTTPException` response wraps `detail` in `{"detail": {...}}`, not the flat `{"error": ...}` shape `contracts/bff-api.md` documents — fixed with a custom exception handler in `main.py` (also added a `dependencies.py::get_scenarios_dir()` + `tests/conftest.py::client` fixture pair, not itemized in plan.md's Project Structure, so tests can isolate scenario storage via `app.dependency_overrides` instead of touching the real `config/scenarios/`)
- [X] T017 [US1] Register the scenarios router in `services/bff/src/rp_bff/main.py` (depends on T009, T016)

**Checkpoint**: User Story 1 is independently functional — quickstart.md §1 passes end-to-end. No reference data (US2), run (US3), comparison (US4), or export (US5) support yet.

---

## Phase 4: User Story 2 - Discover what the engine currently supports (Priority: P2)

**Goal**: A client can retrieve the current, live lists of supported states, withdrawal strategies, conversion strategies, and comparison axes — never a copy that can go stale.

**Independent Test**: Request each reference-data list and confirm it exactly matches directly inspecting `002`'s state-tax registry, `003`'s withdrawal-sequencing/Roth-conversion registries, and `005`'s comparison-axis type — without needing any scenario, simulation, or comparison to exist yet.

### Tests for User Story 2 ⚠️

- [X] T018 [P] [US2] Integration test: `GET /reference/states` returns exactly `002`'s `STATE_MODULES.keys()`, sorted (Acceptance Scenario US2.1) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T019 [US2] Unit test `GET /reference/states` reflects a live change to `STATE_MODULES` (monkeypatch-added temporary entry, via `monkeypatch.setitem` mutating the shared dict object in place) with no code change to this service (Acceptance Scenario US2.2, Principle IV) in `services/bff/tests/unit/test_reference_routes.py`
- [X] T020 [US2] Integration test: `GET /reference/withdrawal-strategies`, `/conversion-strategies`, and `/comparison-axes` each match `003`'s `WITHDRAWAL_STRATEGIES`/`CONVERSION_STRATEGIES` and `005`'s `ComparisonAxis` exactly (Acceptance Scenario US2.3) in `services/bff/tests/integration/test_bff_lifecycle.py`

### Implementation for User Story 2

- [X] T021 [US2] Implement `GET /reference/states`, `/withdrawal-strategies`, `/conversion-strategies`, `/comparison-axes` in `services/bff/src/rp_bff/routes/reference.py`, reading live from `retirement_planner.tax.STATE_MODULES`, `retirement_planner.mechanics.WITHDRAWAL_STRATEGIES`/`CONVERSION_STRATEGIES`, and `typing.get_args(retirement_planner.simulation.models.ComparisonAxis)` (FR-006–FR-007) (depends on T001, T018–T020)
- [X] T022 [US2] Register the reference router in `services/bff/src/rp_bff/main.py` (depends on T009, T021)

**Checkpoint**: User Stories 1–2 are functional — quickstart.md §1–2 pass end-to-end. No run (US3), comparison (US4), or export (US5) support yet.

---

## Phase 5: User Story 3 - Run a simulation and receive a summarized result (Priority: P3)

**Goal**: A client can request a Monte Carlo simulation run against a saved scenario and receive the full run plus its `006`-computed summary in one response.

**Independent Test**: Save one valid scenario, request a run against it with one strategy configuration, and confirm the response's run and summary match calling `005`'s `run_simulation()` and `006`'s `summarize_run()` directly on the same inputs.

### Tests for User Story 3 ⚠️

- [X] T023 [P] [US3] Integration test: `POST /simulations` returns `{"run", "summary"}` matching a direct `run_simulation()`+`summarize_run()` call for the same scenario/strategy/parameters (Acceptance Scenario US3.1) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T024 [US3] Integration test: a run request against a scenario with a blocking validation flag is rejected (422, `blocking_validation_flags`) and no simulation runs (Acceptance Scenario US3.2, FR-009) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T025 [US3] Integration test: the identical run request (including the resolved seed) submitted twice returns identical results (Acceptance Scenario US3.3, FR-010) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T026 [US3] Integration test: a run request omitting `seed`/`n_paths`/`plan_to_age` resolves each from the named scenario's own `simulation_settings`, never a clock or unseeded source (Acceptance Scenario US3.4, FR-011) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T027 [P] [US3] Unit test the request-resolution helper builds a `StrategyConfiguration` whose `claiming_ages` come from each household member's `ss_claim_age` and whose conversion fields come from the scenario's own `roth_conversion` (or all `None` if absent), plus account summation, defaulting, and rejection cases (data-model.md § Run Request/Response) in `services/bff/tests/unit/test_resolution.py`

### Implementation for User Story 3

- [X] T028 [US3] Implement the shared request-resolution helper in `services/bff/src/rp_bff/resolution.py` — loads the named scenario (`ScenarioParseError` propagates for a route to translate to `no_such_scenario`), checks `is_usable`/raises `BlockingValidationFlagsError` if not, builds a `StrategyConfiguration` from the request plus scenario data (summing same-typed `Account` entries into `AccountBalances` — a real `001` schema detail: more than one account of a type is allowed), resolves `plan_to_age`/`n_paths`/`seed` from `simulation_settings` when omitted, and validates `state`/`withdrawal_strategy`/`conversion_strategy` against the live registries raising `UnknownReferenceValueError` if invalid (FR-005, FR-009, FR-011, FR-014, research.md §4, §6) (depends on T004, T010, T021, T023–T027)
- [X] T029 [US3] Wire `estimate_cost_seconds()`/`check_cost_within_budget()` into the resolution helper as `check_run_cost()`, using `deemed_rmd_owner()`'s age to derive `horizon_years` — rejects with `CostBudgetExceededError` before any `004`/`005` call (FR-018) (depends on T008, T028)
- [X] T030 [US3] Implement `POST /simulations` in `services/bff/src/rp_bff/routes/simulations.py` — calls the resolution helper, then `005`'s `generate_return_paths()` + `run_simulation()`, then `006`'s `summarize_run()`, returning `to_jsonable({"run": ..., "summary": ...})`, translating each resolution error to its documented HTTP status (404/422/413) (FR-008) (depends on T006, T028, T029)
- [X] T031 [US3] Register the simulations router in `services/bff/src/rp_bff/main.py` (depends on T009, T030)

**Checkpoint**: User Stories 1–3 are functional — quickstart.md §1–3 pass end-to-end. No comparison (US4) or export (US5) support yet.

---

## Phase 6: User Story 4 - Run and retrieve a comparison (Priority: P4)

**Goal**: A client can request a deterministic or Monte Carlo comparison across a named axis and receive one summarized result per candidate.

**Independent Test**: Save one scenario, request a comparison across two or more candidates on one axis, and confirm the response matches calling the corresponding `004`/`005` comparison function followed by `006`'s corresponding summarization function directly.

### Tests for User Story 4 ⚠️

- [X] T032 [P] [US4] Integration test: `POST /comparisons/simulated` with `axis="state"` and three candidate states returns one summarized result per state, in request order (Acceptance Scenario US4.1) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T033 [US4] Integration test: `POST /comparisons/deterministic` with `axis="roth_conversion_strategy"` returns summaries with `success_rate`/`percentile_bands` explicitly `null`, matching `006`'s deterministic-summary distinction (Acceptance Scenario US4.2) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T034 [US4] Integration test: both comparison endpoints accept a single-candidate request and still return a valid one-entry result (Acceptance Scenario US4.4, FR-015) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T035 [US4] Integration test: a comparison naming an unrecognized axis, or a candidate referencing an unregistered state/strategy, is rejected with the `unknown_reference_value` shape (Acceptance Scenario US4.3, FR-014) in `services/bff/tests/integration/test_bff_lifecycle.py`

### Implementation for User Story 4

- [X] T036 [US4] Implement `POST /comparisons/deterministic` in `services/bff/src/rp_bff/routes/comparisons.py` — dispatches by `axis` (never `"state"`, research.md §7) to `004`'s `compare_roth_conversion_strategies()`/`compare_withdrawal_sequencing_strategies()`/`compare_claiming_age_grid()`, reusing the resolution helper (T028) for scenario/strategy/validation, then `006`'s `summarize_deterministic_comparison()` (FR-012–FR-015) (depends on T028, T032–T035). **Finding**: added `comparison_candidates.py` (not itemized in plan.md's Project Structure) — a small helper converting a comparison request's raw `candidates` list into `StrategyConfiguration` instances for the two axes that need them, with placeholder values in whichever field `004`'s/`005`'s own `compare_*()` immediately overwrites via `dataclasses.replace()` (verified this is safe by reading `004`'s existing `compare.py`, not assumed)
- [X] T037 [US4] Implement `POST /comparisons/simulated` in `services/bff/src/rp_bff/routes/comparisons.py` — dispatches by `axis` (including `"state"`) to `005`'s `compare_states()`/`compare_roth_conversion_strategies()`/`compare_withdrawal_sequencing_strategies()`/`compare_claiming_age_grid()`, reusing the resolution helper plus the cost check (T029) with `candidate_count` now the actual candidate list length, then `006`'s `summarize_simulation_comparison()` (FR-012–FR-015) (depends on T028, T029, T032–T035)
- [X] T038 [US4] Register the comparisons router in `services/bff/src/rp_bff/main.py` (depends on T009, T036, T037)

**Checkpoint**: User Stories 1–4 are functional — quickstart.md §1–4 pass end-to-end. No export (US5) yet.

---

## Phase 7: User Story 5 - Export a run or comparison as a downloadable report (Priority: P5)

**Goal**: A client can request the same run/comparison as a CSV export instead of a JSON response, using the identical request body.

**Independent Test**: Request a CSV export using the same parameters as a successful User Story 3 or User Story 4 request, and confirm the response is well-formed tabular text matching `006`'s corresponding export function on the equivalent run/comparison.

### Tests for User Story 5 ⚠️

- [X] T039 [P] [US5] Integration test: `POST /reports/simulations.csv` with the same body as a successful run request returns `text/csv` with one row per plan year, matching `006`'s `run_to_csv_text()` (Acceptance Scenario US5.1) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T040 [US5] Integration test: `POST /reports/comparisons.csv` (both `engine=deterministic` and `engine=simulated`) with the same body as a successful comparison request returns one row per candidate, clearly labeled (Acceptance Scenario US5.2) in `services/bff/tests/integration/test_bff_lifecycle.py`
- [X] T041 [US5] Integration test: every export response's `has_unverified_figure` column is present and intact, matching `006`'s existing verification-status column (Acceptance Scenario US5.3, FR-017) in `services/bff/tests/integration/test_bff_lifecycle.py`

### Implementation for User Story 5

- [X] T042 [US5] Implement `POST /reports/simulations.csv` in `services/bff/src/rp_bff/routes/reports.py` — reuses `routes/simulations.py`'s `resolve_and_run_simulation()` (extracted from T030 during this story, since US5's whole point is reusing the identical resolve/run path rather than a second copy) then calls `006`'s `run_to_csv_text()` instead of `summarize_run()`, returning a `text/csv` response (FR-016–FR-017) (depends on T028, T030, T039–T041)
- [X] T043 [US5] Implement `POST /reports/comparisons.csv` in `services/bff/src/rp_bff/routes/reports.py` — reuses `routes/comparisons.py`'s `resolve_and_compare_deterministic()`/`resolve_and_compare_simulated()` (extracted from T036/T037 during this story), dispatching to `006`'s `deterministic_comparison_to_csv_text()`/`simulation_comparison_to_csv_text()` by the `engine` query parameter (FR-016–FR-017) (depends on T036, T037, T039–T041)
- [X] T044 [US5] Register the reports router in `services/bff/src/rp_bff/main.py` (depends on T009, T042, T043)

**Checkpoint**: All five user stories are independently functional — scenario management, reference data, simulation runs, comparisons of both kinds, and CSV export, per [quickstart.md](./quickstart.md) steps 1–5.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify this feature's cross-cutting requirements (the dependency containment boundary, the cost-rejection path end-to-end, the auto-generated API docs) and tie the quickstart walkthrough together as one acceptance run

- [X] T045 Run the complete [quickstart.md](./quickstart.md) walkthrough (all 5 sections) as one end-to-end assertion sequence in `services/bff/tests/integration/test_bff_lifecycle.py` — satisfied by construction: the file was built incrementally per section throughout US1–US5 and all 38 of its tests already run and pass together as one suite (depends on T011–T015, T018–T020, T023–T027, T032–T035, T039–T041)
- [X] T046 [P] Integration test: a run or comparison request whose estimated cost exceeds the 30-second threshold (`n_paths=10_000` against the 36-year reference scenario) is rejected with the `estimated_cost_exceeds_budget` shape via a real HTTP call, completing fast since rejection happens pre-flight — not only the unit-level estimator test (FR-018, plan.md Performance Goals) in `services/bff/tests/integration/test_bff_lifecycle.py` (depends on T029)
- [X] T047 [P] Confirm the repository-root `pyproject.toml` (core `retirement_planner` package) has zero new dependencies after this feature — both a manual `git diff -- pyproject.toml` (empty) and a permanent pytest check (`test_dependency_containment.py`, parsed via `tomllib`) asserting the Constitution Check's containment-boundary claim empirically, not just by convention (depends on T001)
- [X] T048 [P] Confirm FastAPI's auto-generated `/docs` (Swagger UI) and `/openapi.json` are reachable and enumerate every route this feature registers — the manual-testing surface `docs/frontend_architecture.md` §2 named as a benefit of choosing FastAPI (depends on T017, T022, T031, T038, T044)
- [X] T049 [P] Add docstrings to every public function/route handler in `services/bff/src/rp_bff/{serialization,cost_estimation,resolution,main,comparison_candidates,schemas}.py` and each `routes/*.py` module, referencing the corresponding section of [contracts/bff-api.md](./contracts/bff-api.md) (depends on T017, T022, T031, T038, T044). **Finding**: running `pytest services/bff/tests/ tests/` together in one invocation fails with `ModuleNotFoundError` — both packages' `tests/integration/` directories collide as the same top-level module name `integration` under pytest's default import mode; this is a pre-existing consequence of the two-package layout (plan.md's Structure Decision), not a regression — the two suites are run independently (`pytest tests/` from repo root; `pytest services/bff/tests/` for the new package), exactly as `services/bff/pyproject.toml`'s own `testpaths` config already implies

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational only — independent of User Story 1
- **User Story 3 (Phase 5)**: Depends on Foundational **and** User Story 1 (a scenario must be saveable/loadable before a run can resolve one) — independent of User Story 2, though a real client would use US2's reference data to build a valid request
- **User Story 4 (Phase 6)**: Depends on User Story 3's resolution helper (T028) and cost check (T029) directly
- **User Story 5 (Phase 7)**: Depends on User Story 3's (T028, T030) and User Story 4's (T036, T037) resolution/dispatch logic directly
- **Polish (Phase 8)**: `T045` depends on all five user stories' integration tests; `T046` depends on T029; `T047` depends on T001; `T048`/`T049` depend on every story's router registration

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — the MVP slice
- **User Story 2 (P2)**: No dependency on User Story 1 or any other story — can be built fully in parallel with User Story 1 once Foundational is done
- **User Story 3 (P3)**: Depends on User Story 1 (needs a resolvable scenario); no dependency on User Story 2
- **User Story 4 (P4)**: Depends on User Story 3's resolution helper; no dependency on User Story 2
- **User Story 5 (P5)**: Depends on both User Story 3's and User Story 4's request-handling logic
- Unlike `004`'s four independent stories, this feature's later stories are genuinely sequential relative to User Story 3 (see the note at the top of this document) — but **User Story 1 and User Story 2 are fully independent of each other** and can be built in parallel from the start

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task
- Foundational's `delete_scenario()` (T004), `to_jsonable()` (T006), `estimate_cost_seconds()` (T008), the base app (T009), and base schemas (T010) before any story-specific route code
- Within User Story 3: the resolution helper (T028) before the cost-check wiring (T029), before the route handler itself (T030)
- Within User Story 4: the deterministic (T036) and simulated (T037) route handlers have no dependency on each other beyond both needing T028/T029 — they can be implemented in parallel
- Within User Story 5: the run-export (T042) and comparison-export (T043) route handlers likewise have no dependency on each other

### Parallel Opportunities

- T001 has no dependency; T003/T005/T007/T009/T010 can all start in parallel once T001 (and, for T002-dependent ones, T002) is done — five genuinely independent pieces of foundational infrastructure in five different files
- **User Story 1 and User Story 2 can be built fully in parallel** by different contributors once Foundational is done — neither depends on the other
- Within User Story 4: T036 and T037 can be implemented in parallel (different functions, same file — coordinate on merge order within `routes/comparisons.py`)
- Within User Story 5: T042 and T043 can be implemented in parallel (different functions, same file — coordinate on merge order within `routes/reports.py`)
- T046/T047/T048/T049 in Polish can all run in parallel — four independent verification concerns

---

## Parallel Example: Foundational phase

```bash
# Launch five independent foundational pieces together, once T001/T002 are done:
Task: "Unit test delete_scenario() in tests/unit/scenario/test_store.py"
Task: "Unit test to_jsonable() in services/bff/tests/unit/test_serialization.py"
Task: "Unit test estimate_cost_seconds() in services/bff/tests/unit/test_cost_estimation.py"
Task: "Wire the base FastAPI app in services/bff/src/rp_bff/main.py"
Task: "Define ScenarioRequest/ScenarioResponse in services/bff/src/rp_bff/schemas.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest services/bff/tests/` and confirm SC-001 holds via quickstart.md §1
5. This alone proves the HTTP boundary and the scenario-management round trip every later story builds on

### Incremental Delivery

1. Setup + Foundational → foundation ready (the `001` prerequisite, serializer, cost estimator, and base app are live)
2. Add User Story 1 → scenario CRUD over HTTP → validate independently (SC-001) → this is the MVP
3. Add User Story 2 (in parallel with User Story 1, if staffed) → live reference data → validate independently (SC-002)
4. Add User Story 3 → simulation runs → validate independently (SC-003, SC-006)
5. Add User Story 4 → comparisons of both kinds → validate independently (SC-004)
6. Add User Story 5 → CSV export → validate independently (SC-005, SC-007)
7. Polish → full quickstart.md walkthrough, cost-rejection path, dependency containment check, `/docs` sanity check, docstrings (SC-008)

### Suggested Team Split

User Story 1 and User Story 2 can be split across two contributors immediately after Foundational, since neither depends on the other. User Story 3 must wait for User Story 1 (it needs a resolvable scenario) but not User Story 2. Once User Story 3's resolution helper (T028) is merged, User Story 4's two comparison handlers (T036, T037) can be split across two contributors; once User Story 4 is merged, User Story 5's two export handlers (T042, T043) can likewise be split. This feature has less opportunity for full-story parallelism than `004`/`005` did, since three of its five stories (US3→US4→US5) form a genuine dependency chain — the useful parallelism here is *within* each of those later stories, not across them.
