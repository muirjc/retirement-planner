---

description: "Task list for Federal & State Tax Calculation Engine"
---

# Tasks: Federal & State Tax Calculation Engine

**Input**: Design documents from `/specs/002-tax-calculation-engine/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/tax-api.md](./contracts/tax-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Project Structure and the constitution's Development Workflow gate ("unit test coverage for numeric primitives") both specify test files as deliverables of this feature, matching the precedent set by `001-scenario-config-management`.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and relative to the repository root

## Path Conventions

Single Python library project, `src/` layout, per [plan.md](./plan.md) Project Structure:
- Library code: `src/retirement_planner/tax/`
- Tests: `tests/unit/tax/`, `tests/integration/`

No new runtime dependencies are needed (research.md §1) — `pyproject.toml` is unchanged.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create the tax subpackage directory skeleton: `src/retirement_planner/tax/__init__.py`, `src/retirement_planner/tax/state/__init__.py`, `tests/unit/tax/__init__.py` (mirrors `001`'s `scenario/` layout; `tests/integration/` already exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data shapes every user story's code and tests are built on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Define all shared tax data types in `src/retirement_planner/tax/models.py`: `FilingStatus`, `IncomeComponents`, `BracketRow`, `BracketTable`, `SourcedFigure` (generic, with a `value_for_year()` method that raises `UnsupportedTaxYearError` for a year not in its schedule), `FigureUsage`, `FederalTaxResult`, `StateTaxResult`, `UnsupportedTaxYearError`, exactly matching the shapes in [data-model.md](./data-model.md) and [contracts/tax-api.md](./contracts/tax-api.md)
- [X] T003 Wire the public exports in `src/retirement_planner/tax/__init__.py` — re-export every type from T002 (function exports from `social_security.py`, `federal.py`, and `state/` are added as their user stories land) (depends on T002)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Compute accurate federal tax, including real Social Security taxability (Priority: P1) 🎯 MVP

**Goal**: Given a household's filing status, ordinary income, and Social Security gross benefit for a tax year, compute federal tax using genuine progressive bracket math and the real 0%/50%/85% provisional-income taxability rule.

**Independent Test**: Feed a range of reference incomes (below, between, and above each provisional-income threshold) into the calculation and confirm the results match hand-calculated values.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T008–T009

- [X] T004 [P] [US1] Unit test `compute_taxable_social_security()` across all three provisional-income tiers — 0%, up-to-50%, up-to-85% inclusion (Acceptance Scenarios 1.2–1.4) in `tests/unit/tax/test_social_security.py`
- [X] T005 [US1] Unit test `compute_taxable_social_security()` raises `UnsupportedTaxYearError` for a tax year with no threshold schedule entry in `tests/unit/tax/test_social_security.py`
- [X] T006 [P] [US1] Unit test `compute_federal_tax()` against published/hand-calculated reference incomes for both `single` and `married_filing_jointly` (SC-001, Acceptance Scenario 1.1) in `tests/unit/tax/test_federal.py`
- [X] T007 [US1] Unit test `compute_federal_tax()` correctly combines ordinary income with the taxable portion of Social Security (from `compute_taxable_social_security()`) before applying bracket math in `tests/unit/tax/test_federal.py`

### Implementation for User Story 1

- [X] T008 [US1] Implement `compute_taxable_social_security()` in `src/retirement_planner/tax/social_security.py` — the federal provisional-income formula (FR-002), backed by a `SourcedFigure` pair for the two thresholds, scheduled for tax year 2026 (illustrative/placeholder rates and citation per quickstart.md, `verified=False`) (depends on T002)
- [X] T009 [US1] Implement `compute_federal_tax()` in `src/retirement_planner/tax/federal.py` — a federal bracket table as `SourcedFigure[BracketTable]` (tax year 2026, `verified=False`), genuine progressive bracket math, calling `compute_taxable_social_security()` internally (FR-001, FR-003) (depends on T002, T008)
- [X] T010 [US1] Add `compute_taxable_social_security` and `compute_federal_tax` to `src/retirement_planner/tax/__init__.py` exports (depends on T008, T009)
- [X] T011 [US1] Integration test: run quickstart.md step 1 (federal tax across all three Social Security taxability tiers) in `tests/integration/test_tax_lifecycle.py` (depends on T009)

**Checkpoint**: User Story 1 is independently functional — federal tax can be computed correctly, including real Social Security taxability. No state tax (US2) or figure-provenance/schedule behavior (US3) yet.

---

## Phase 4: User Story 2 - Compute state tax through real, pluggable per-state modules (Priority: P2)

**Goal**: Given a household's income, ages, filing status, state, and tax year, compute state tax through that state's own independent module — genuine bracket-by-bracket math for South Carolina and Delaware, zero tax for Florida.

**Independent Test**: Compute tax for the same household under each state module and confirm each matches a hand-calculated example for that state's actual rules, and that computing one state never affects another.

### Tests for User Story 2 ⚠️

- [X] T012 [P] [US2] Unit test South Carolina's `compute_tax()` against a hand-calculated bracket example (SC-002, Acceptance Scenario 2.2) in `tests/unit/tax/test_state_sc.py`
- [X] T013 [P] [US2] Unit test Delaware's `compute_tax()` against a hand-calculated bracket example (SC-002, Acceptance Scenario 2.2) in `tests/unit/tax/test_state_de.py`
- [X] T014 [P] [US2] Unit test Florida's `compute_tax()` always returns zero tax and an empty `figures_used` list (FR-007, Acceptance Scenario 2.3) in `tests/unit/tax/test_state_fl.py`
- [X] T015 [P] [US2] Unit test `compute_state_tax()` dispatches through `STATE_MODULES` by state code, and that computing tax for one state never mutates or affects another state's result (FR-005, Acceptance Scenario 2.1, 2.4) in `tests/unit/tax/test_state_dispatch.py`

### Implementation for User Story 2

- [X] T016 [P] [US2] Implement South Carolina's `compute_tax()` in `src/retirement_planner/tax/state/sc.py` — genuine bracket-by-bracket math against a `SourcedFigure[BracketTable]` (tax year 2026) plus its age-based exclusion figure(s), `verified=False` (FR-006) (depends on T002)
- [X] T017 [P] [US2] Implement Delaware's `compute_tax()` in `src/retirement_planner/tax/state/de.py` — genuine bracket-by-bracket math against a `SourcedFigure[BracketTable]` (tax year 2026) plus its age-based exclusion figure, `verified=False` (FR-006) (depends on T002)
- [X] T018 [P] [US2] Implement Florida's `compute_tax()` in `src/retirement_planner/tax/state/fl.py` — always returns zero tax with an empty `figures_used` list, no figure lookups (FR-007) (depends on T002)
- [X] T019 [US2] Implement the `STATE_MODULES` registry and `compute_state_tax()` dispatcher in `src/retirement_planner/tax/state/__init__.py`, registering `"SC"`, `"DE"`, `"FL"` (FR-005, SC-006) (depends on T016, T017, T018)
- [X] T020 [US2] Add `compute_state_tax` and `STATE_MODULES` to `src/retirement_planner/tax/__init__.py` exports (depends on T019)
- [X] T021 [US2] Integration test: run quickstart.md step 2 (SC/DE non-zero via real bracket math, FL zero with no figures consulted, independence between states) in `tests/integration/test_tax_lifecycle.py` (depends on T019)

**Checkpoint**: User Stories 1 and 2 are both independently functional — federal and state tax can each be computed correctly and independently. Every figure still only has one documented tax year (2026); multi-year schedules (US3) aren't exercised yet.

---

## Phase 5: User Story 3 - See which figures are unverified, and get correct results across tax years with scheduled law changes (Priority: P3)

**Goal**: Every computed result's figures are individually traceable to a citation/date/verification status, and a figure with a documented multi-year schedule produces the correct year-specific result — while a genuinely out-of-schedule year is refused, not guessed.

**Independent Test**: Inspect the figures behind a computed result; request the same state's tax for two documented years on either side of a scheduled change; request a tax year with no schedule entry and confirm a clear refusal.

### Tests for User Story 3 ⚠️

- [X] T022 [P] [US3] Unit test every entry in a `FederalTaxResult`/`StateTaxResult`'s `figures_used` carries a name, citation, `last_verified` date, and `verified=False` by default (FR-009–FR-011, Acceptance Scenarios 3.1–3.2) in `tests/unit/tax/test_figure_tracking.py`
- [X] T023 [US3] Unit test South Carolina's tax, computed for two documented tax years (2026 and 2027) on either side of a scheduled rate change, produces two different, independently correct results (FR-012, Acceptance Scenario 3.3) in `tests/unit/tax/test_figure_tracking.py`
- [X] T024 [US3] Unit test requesting a tax year with no schedule entry for a given figure raises `UnsupportedTaxYearError` naming the figure, the requested year, and the years that are documented (FR-016, Acceptance Scenario 3.4) in `tests/unit/tax/test_figure_tracking.py`

### Implementation for User Story 3

- [X] T025 [US3] Add a second documented tax year (2027, a different rate — illustrative/placeholder, `verified=False`) to South Carolina's bracket-table `SourcedFigure` in `src/retirement_planner/tax/state/sc.py`, giving FR-012's schedule mechanic a real example to exercise (depends on T016) — *landed as part of T016's single edit rather than as a separate follow-up change; verified here by T022–T024's passing tests.*
- [X] T026 [US3] Integration test: run quickstart.md step 3 (figure provenance inspection, SC's 2026-vs-2027 schedule change, `UnsupportedTaxYearError` for a far-out-of-range year) in `tests/integration/test_tax_lifecycle.py` (depends on T021, T025)

**Checkpoint**: All three user stories are independently functional and integrated — federal tax, state tax, and figure provenance/scheduling all work correctly together, per [quickstart.md](./quickstart.md).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify the feature as a whole against the spec's non-story requirements

- [X] T027 Run the complete [quickstart.md](./quickstart.md) walkthrough (all 3 steps) as one end-to-end assertion sequence — computing federal and state tax for the same household together, then inspecting figure provenance — in `tests/integration/test_tax_lifecycle.py` (depends on T011, T021, T026)
- [X] T028 Add docstrings to every public function/dataclass in `src/retirement_planner/tax/{models,social_security,federal}.py` and `src/retirement_planner/tax/state/{__init__,sc,de,fl}.py` referencing the corresponding section of [contracts/tax-api.md](./contracts/tax-api.md) (depends on T009, T019, T025)
- [X] T029 [P] Add a lightweight timing check confirming a single federal-plus-state computation completes in well under 10ms (plan.md Performance Goals) in `tests/integration/test_tax_performance.py` (depends on T009, T019)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational only — does not need US1's federal calculation to exist, since state tax is computed independently of federal tax
- **User Story 3 (Phase 5)**: Depends on Foundational directly (figure-shape tests, T022, T024) and on US2's `sc.py` (T025 extends it with a second schedule year; T023/T026 exercise that extension)
- **Polish (Phase 6)**: Depends on all three user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — the MVP slice
- **User Story 2 (P2)**: No dependency on US1 — federal and state calculations are independent of each other by design (data-model.md § Relationships); can be built in parallel with US1 once Foundational is done
- **User Story 3 (P3)**: Reuses US2's `sc.py` (T025 depends on T016), but the figure-shape assertions (T022) only need Foundational's `models.py` and either story's results

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task
- Foundational models before any story-specific code
- Within US1: `social_security.py` before `federal.py` (federal calls into SS taxability)
- Within US2: the three state modules before the registry/dispatcher that wires them together

### Parallel Opportunities

- T004 and T006 (US1 tests, different files) can run in parallel
- T012, T013, T014, and T015 (US2 tests, four different files) can all run in parallel
- T016, T017, and T018 (US2 state module implementations, three different files) can all run in parallel — none depends on another, only on Foundational
- T022 (US3 test, new file) can start in parallel with US1/US2 tasks once Foundational is done
- **User Story 1 and User Story 2 can be built fully in parallel** by different contributors once Foundational is done, since neither depends on the other's code (only US3 depends on US2's `sc.py`)
- T029 (performance check) can run in parallel with T027/T028 — separate file

---

## Parallel Example: User Story 2

```bash
# Launch all four new-file tests for User Story 2 together:
Task: "Unit test SC compute_tax() in tests/unit/tax/test_state_sc.py"
Task: "Unit test DE compute_tax() in tests/unit/tax/test_state_de.py"
Task: "Unit test FL compute_tax() in tests/unit/tax/test_state_fl.py"
Task: "Unit test compute_state_tax() dispatch in tests/unit/tax/test_state_dispatch.py"

# Launch all three state module implementations together:
Task: "Implement SC compute_tax() in src/retirement_planner/tax/state/sc.py"
Task: "Implement DE compute_tax() in src/retirement_planner/tax/state/de.py"
Task: "Implement FL compute_tax() in src/retirement_planner/tax/state/fl.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest tests/unit/tax/test_social_security.py tests/unit/tax/test_federal.py tests/integration/test_tax_lifecycle.py` and confirm SC-001 holds
5. This alone proves federal tax — the number every other part of the tool depends on most directly — is computed accurately, including the source document's single highest-priority accuracy fix (real Social Security taxability)

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add User Story 1 → accurate federal tax → validate independently (SC-001) → this is the MVP
3. Add User Story 2 → real per-state tax via pluggable modules → validate independently (SC-002, SC-006)
4. Add User Story 3 → figure provenance + scheduled rate changes → validate independently (SC-003, SC-004, SC-005)
5. Polish → full quickstart.md walkthrough + performance check

### Suggested Team Split

User Story 1 and User Story 2 can be built fully in parallel by different contributors once Foundational is done — they share only `models.py` (already built) and don't call into each other. User Story 3 is the natural next step for whoever finishes US2 first, since it extends `sc.py`.
