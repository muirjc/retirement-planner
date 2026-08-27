---

description: "Task list for Scenario Configuration & Validation"
---

# Tasks: Scenario Configuration & Validation

**Input**: Design documents from `/specs/001-scenario-config-management/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/scenario-api.md](./contracts/scenario-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Project Structure and quickstart.md's "Running the automated version" section both specify a `tests/` tree and named pytest files as deliverables of this feature, so test tasks are generated per user story.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and relative to the repository root

## Path Conventions

Single Python library project, `src/` layout, per [plan.md](./plan.md) Project Structure:
- Library code: `src/retirement_planner/scenario/`
- Scenario data files: `config/scenarios/`
- Tests: `tests/unit/scenario/`, `tests/integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create the project directory skeleton: `config/scenarios/.gitkeep`, `src/retirement_planner/__init__.py`, `src/retirement_planner/scenario/__init__.py`, `tests/unit/scenario/__init__.py`, `tests/integration/__init__.py`
- [X] T002 Initialize Python packaging in `pyproject.toml` at the repo root — Python `>=3.11`, `src`-layout package discovery for `retirement_planner`, dependencies `pyyaml` and `pytest` (per [research.md](./research.md) §1, §2, §4)
- [X] T003 [P] Add `tests/conftest.py` with a pytest fixture that points scenario storage at a temporary directory (`tmp_path`) for every test, so no test ever reads or writes the real `config/scenarios/` directory

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data shapes every user story's code and tests are built on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Define all scenario dataclasses in `src/retirement_planner/scenario/models.py`: `HouseholdMember`, `Household`, `Account`, `SpendingProfile`, `RothConversionPlan`, `MarketAssumptions`, `SimulationSettings`, `ValidationFlag`, and `Scenario` (including the `is_usable` property), exactly matching the shapes in [data-model.md](./data-model.md) and [contracts/scenario-api.md](./contracts/scenario-api.md)
- [X] T005 [P] Define the `ScenarioParseError` exception class in `src/retirement_planner/scenario/loader.py` (constructor takes `source` and `reason`, per contracts/scenario-api.md) — the real `parse_scenario()` implementation is built in Phase 3 (US1)
- [X] T006 [P] Add a stub `validate(scenario) -> list[ValidationFlag]` in `src/retirement_planner/scenario/validation.py` that always returns `[]`, so scenario-loading code in later phases has a stable call target before the real rules are added in Phase 5 (US3)
- [X] T007 Wire the public exports in `src/retirement_planner/scenario/__init__.py` — re-export the models from T004, `ScenarioParseError` from T005, and `validate` from T006 (depends on T004, T005, T006)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Describe a retirement scenario without touching code (Priority: P1) 🎯 MVP

**Goal**: A user can author a scenario as a YAML config file and have it loaded into a fully structured, in-memory representation — no code edits, no simulation run.

**Independent Test**: Author a config file with a complete household/account/spending/market profile and load it via `parse_scenario()`, confirming every authored field is present, correctly typed, and that a missing-field or malformed-file config is reported distinctly instead of silently accepted.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T013

- [X] T008 [P] [US1] Unit test scenario dataclass construction and field access (all entities from T004 build correctly and expose their fields) in `tests/unit/scenario/test_models.py`
- [X] T009 [P] [US1] Unit test `parse_scenario()` happy path — full YAML profile (household, accounts, spending, roth_conversion, state, market_assumptions, simulation_settings) parses into a `Scenario` with every field accessible by name (Acceptance Scenario 1.1) in `tests/unit/scenario/test_loader.py`
- [X] T010 [US1] Unit test `parse_scenario()` reports the specific missing field when a required value (e.g., an account balance) is absent, instead of loading a partial/defaulted scenario (Acceptance Scenario 1.2, FR-010) in `tests/unit/scenario/test_loader.py`
- [X] T011 [US1] Unit test `parse_scenario()` raises `ScenarioParseError` for syntactically malformed YAML, distinct from a value-level problem (FR-012, Edge Cases) in `tests/unit/scenario/test_loader.py`
- [X] T012 [US1] Unit test `parse_scenario()` raises `ScenarioParseError` when `household.members` length doesn't match `filing_status` (1 for single, 2 for married_filing_jointly) in `tests/unit/scenario/test_loader.py`

### Implementation for User Story 1

- [X] T013 [US1] Implement `parse_scenario(yaml_text, *, name=None) -> Scenario` in `src/retirement_planner/scenario/loader.py` — parse with `yaml.safe_load`, build the nested dataclass tree from T004, and raise `ScenarioParseError` (naming the offending field) for malformed YAML, missing required fields, and household member-count/filing_status mismatches (depends on T004, T005)
- [X] T014 [US1] Integration test: author a complete scenario YAML fixture, load it with `parse_scenario()`, confirm all fields round-trip, and confirm that changing a single value and re-parsing changes only that field (Acceptance Scenario 1.3) in `tests/integration/test_scenario_lifecycle.py` (depends on T013)

**Checkpoint**: User Story 1 is independently functional — a scenario can be authored and parsed into a structured representation with parse-level error reporting. No named-scenario storage (US2) or value-level validation (US3) yet.

---

## Phase 4: User Story 2 - Maintain multiple named scenarios for comparison (Priority: P2)

**Goal**: A user can save a scenario under a distinct name, list every saved scenario, and reload any one of them — with zero cross-contamination between named scenarios.

**Independent Test**: Save two or more distinctly named scenarios, list them, reload each independently, and confirm editing/saving one never alters another's stored data.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Unit test `save_scenario()` → `list_scenarios()` → `load_scenario()` round trip for at least 10 distinctly named scenarios, confirming every one remains fully isolated from all the others (FR-003–FR-005, SC-003) in `tests/unit/scenario/test_store.py`
- [X] T016 [US2] Unit test `save_scenario()` overwrites any existing saved scenario of the same name (FR-015) in `tests/unit/scenario/test_store.py`

### Implementation for User Story 2

- [X] T017 [US2] Implement `save_scenario(scenario, *, scenarios_dir=None)`, `list_scenarios(*, scenarios_dir=None)`, and `load_scenario(name, *, scenarios_dir=None) -> Scenario` in `src/retirement_planner/scenario/store.py` — one YAML file per scenario name under `config/scenarios/` (filename sanitized from the scenario name), overwrite-on-save, and `load_scenario` combining `loader.parse_scenario()` with `validation.validate()` to populate `Scenario.validation_flags` (depends on T013, T006; `scenarios_dir` param exists so T003's fixture can redirect storage during tests)
- [X] T018 [US2] Integration test: save `base_case` and `high_spending` scenarios, confirm `list_scenarios()` returns both, and confirm reloading `base_case` after editing/saving `high_spending` shows `base_case` untouched (Acceptance Scenarios 2.1–2.3, SC-003) in `tests/integration/test_scenario_lifecycle.py` (depends on T017)

**Checkpoint**: User Stories 1 and 2 are both independently functional — scenarios can be authored, saved under distinct names, listed, and reloaded with no cross-contamination. Validation flags are still always empty (Phase 2 stub) until Phase 5.

---

## Phase 5: User Story 3 - Catch impossible or out-of-range inputs before they're used (Priority: P3)

**Goal**: A loaded scenario immediately surfaces every value-level problem it contains — blocking for impossible values, warning for plausibility concerns — each naming the field and the reason.

**Independent Test**: Author configs that each violate exactly one validation rule and confirm each is flagged with the right field, message, and severity; confirm a clean scenario raises no flags.

### Tests for User Story 3 ⚠️

- [X] T019 [P] [US3] Unit test `validate()` flags a negative account balance as `blocking`, with field path `accounts[<type>].balance` (FR-007, FR-011) in `tests/unit/scenario/test_validation.py`
- [X] T020 [US3] Unit test `validate()` flags `ss_claim_age` outside 62–70 as `blocking` for the correct household member, and accepts the boundary values 62 and 70 without flagging (FR-008, Edge Cases) in `tests/unit/scenario/test_validation.py`
- [X] T021 [US3] Unit test `validate()` flags negative `ss_annual_benefit` and negative `annual_need_real` as `blocking`, and accepts `annual_need_real == 0` without flagging (FR-007, Edge Cases) in `tests/unit/scenario/test_validation.py`
- [X] T022 [US3] Unit test `validate()` flags the spending-vs-assets plausibility concern (`annual_need_real × plan horizon > total starting assets`) as `warning`, and confirms `Scenario.is_usable` stays `True` in that case (FR-009, FR-014) in `tests/unit/scenario/test_validation.py`
- [X] T023 [US3] Unit test `validate()` returns `[]` and `Scenario.is_usable` is `True` for a scenario with no problems (Acceptance Scenario 3.4) in `tests/unit/scenario/test_validation.py`

### Implementation for User Story 3

- [X] T024 [US3] Implement the full `validate(scenario) -> list[ValidationFlag]` rule set in `src/retirement_planner/scenario/validation.py`, replacing the Phase 2 stub — account balance negativity, `ss_claim_age` range, `ss_annual_benefit` negativity, spending negativity, and the spending-vs-assets plausibility check (horizon = `plan_to_age` − older member's `current_age`; assets = sum of all account balances) — each producing a `ValidationFlag` with a dotted field path, a plain-language message, and the correct severity, per [data-model.md](./data-model.md) (depends on T004, T006)
- [X] T025 [US3] Integration test: load a scenario with two simultaneous problems (out-of-range claiming age + negative balance) and confirm both are reported together, each naming its own field and reason (FR-006, FR-011, Acceptance Scenarios 3.1–3.3) in `tests/integration/test_scenario_lifecycle.py` (depends on T017, T024)

**Checkpoint**: All three user stories are independently functional and integrated — the full scenario lifecycle (author → save → list → load → validate) works end-to-end per [quickstart.md](./quickstart.md).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify the feature as a whole against the spec's non-story requirements

- [X] T026 Integration test confirming the malformed-file-vs-value-validation distinction end-to-end: `load_scenario()` on an unparseable saved file raises `ScenarioParseError`, never a `ValidationFlag` (FR-012, quickstart.md step 5) in `tests/integration/test_scenario_lifecycle.py` (depends on T013, T017)
- [X] T027 Run the complete [quickstart.md](./quickstart.md) walkthrough (all 5 steps) as one end-to-end assertion sequence in `tests/integration/test_scenario_lifecycle.py` (depends on T014, T018, T025, T026)
- [X] T028 [P] Add a lightweight timing check confirming save/list/load/validate for one scenario each complete in well under 1 second (plan.md Performance Goals) in `tests/integration/test_performance.py` (depends on T017, T024)
- [X] T029 Add docstrings to every public function/dataclass in `src/retirement_planner/scenario/{models,loader,store,validation}.py` referencing the corresponding section of [contracts/scenario-api.md](./contracts/scenario-api.md) (depends on T013, T017, T024)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational; its `load_scenario()` (T017) depends on US1's `parse_scenario()` (T013)
- **User Story 3 (Phase 5)**: Depends on Foundational; its integration test (T025) depends on US2's `store.py` (T017) to exercise the full load path
- **Polish (Phase 6)**: Depends on all three user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — the MVP slice
- **User Story 2 (P2)**: Reuses US1's `parse_scenario()` internally (T017 depends on T013) but is independently testable via its own save/list/load round trip
- **User Story 3 (P3)**: Reuses US2's `store.py` for its integration test (T025 depends on T017), but `validate()` itself (T024) only depends on the Foundational models and is independently unit-testable

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task
- Models (Foundational) before loader (US1) before store (US2) before validation rules (US3)
- Unit tests before integration tests within a phase

### Parallel Opportunities

- T002 and T003 (Setup) can run in parallel — different files
- T005 and T006 (Foundational) can run in parallel with each other and with T004 — different files, no cross-dependency for stub definitions
- T008 and T009 (US1 tests) can run in parallel — different files
- T015 (US2 test) can start in parallel with US1 tasks once Foundational is done, though its implementation (T017) still waits on T013
- T019 (US3 test) can start in parallel with US1/US2 tasks once Foundational is done, though its implementation (T024) only needs T004/T006
- T028 (performance check) can run in parallel with T026/T027/T029 — separate file

---

## Parallel Example: User Story 1

```bash
# Launch both new-file tests for User Story 1 together:
Task: "Unit test scenario dataclass construction in tests/unit/scenario/test_models.py"
Task: "Unit test parse_scenario() happy path in tests/unit/scenario/test_loader.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest tests/unit/scenario/test_models.py tests/unit/scenario/test_loader.py tests/integration/test_scenario_lifecycle.py::test_user_story_1*` (or equivalent) and confirm SC-001/SC-004 hold
5. This alone proves scenarios can be authored as data with zero code edits — the foundation everything else in the source requirement document builds on

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add User Story 1 → parse a scenario from YAML → validate independently → this is the MVP
3. Add User Story 2 → named save/list/load with isolation → validate independently (SC-003)
4. Add User Story 3 → value-level validation flags → validate independently (SC-002, SC-005)
5. Polish → full quickstart.md walkthrough + performance check

### Suggested Team Split

With more than one contributor, User Story 2 and User Story 3 can be built in parallel once Foundational and US1's `parse_scenario()` (T013) exist, since T017 only needs T013 and T024 only needs T004/T006 — they converge only at the Phase 5/6 integration tests.
