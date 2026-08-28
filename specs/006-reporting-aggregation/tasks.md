---

description: "Task list for Reporting & Aggregation"
---

# Tasks: Reporting & Aggregation

**Input**: Design documents from `/specs/006-reporting-aggregation/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/reporting-api.md](./contracts/reporting-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Project Structure and the constitution's Development Workflow gate ("unit test coverage for numeric primitives") both specify test files as deliverables of this feature, matching the precedent set by `001`–`005`.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P4) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- File paths are exact and relative to the repository root

## Path Conventions

Single Python library project, `src/` layout, per [plan.md](./plan.md) Project Structure:
- Library code: `src/retirement_planner/reporting/`, plus one additive rename in `src/retirement_planner/comparison/{projection,__init__}.py`
- Tests: `tests/unit/reporting/`, `tests/unit/comparison/`, `tests/integration/`

No new runtime dependencies (plan.md Technical Context) — `pyproject.toml` is unchanged; this feature uses only `dataclasses`, `statistics`, `csv`, and `io` from the standard library. This feature imports from `retirement_planner.scenario`, `retirement_planner.tax`, `retirement_planner.comparison`, and `retirement_planner.simulation`; only `comparison/projection.py` and `comparison/__init__.py` change outside this feature's own subpackage (research.md §1) — no other file in `001`–`005` changes.

**This feature's stories build on each other more than `001`–`003` did but less than `004`/`005` did**: User Story 1's `summarize_run()` is the base every other story reuses — User Story 2's comparison functions are thin loops over it (or, for the deterministic case, over the same logic applied to one `PlanProjection`), and User Story 3's comparison exporters call User Story 2's functions directly. User Story 3's single-run exporter (`run_to_csv_text()`) only needs Foundational (it reads `SimulationRun` fields directly, not through `summarize_run()` — see research.md §7). User Story 4 adds **no new implementation** — it is a dedicated verification pass confirming behavior User Story 1 and User Story 3 already deliver (unverified-figure surfacing was a Functional Requirement of both from the start), so its phase contains tests only.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create the reporting subpackage directory skeleton: `src/retirement_planner/reporting/__init__.py`, `tests/unit/reporting/__init__.py` (mirrors `005`'s `simulation/` layout; `tests/integration/` already exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The reused age-translation helpers from `004`, and the shared `SummaryStatistics` shape every user story returns

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Rename `_member_age_in_tax_year` → `member_age_in_tax_year` and `_deemed_rmd_owner` → `deemed_rmd_owner` in `src/retirement_planner/comparison/projection.py` (update internal call sites), export both from `src/retirement_planner/comparison/__init__.py`, and update `tests/unit/comparison/test_projection.py`'s imports to the new public names (research.md §1) — `pytest tests/unit/comparison/` confirms `004`'s existing behavior is unchanged (27/27 passed)
- [X] T003 [P] Define `SummaryStatistics` in `src/retirement_planner/reporting/models.py` — importing `PercentileBand` from `retirement_planner.simulation` rather than redefining it, exactly matching [data-model.md](./data-model.md) and [contracts/reporting-api.md](./contracts/reporting-api.md)
- [X] T004 Wire base exports in `src/retirement_planner/reporting/__init__.py` — re-export `SummaryStatistics` from T003 (function exports are added per story below) (depends on T003)

**Checkpoint**: Foundation ready — User Story 1 implementation can now begin

---

## Phase 3: User Story 1 - Get a decision-ready summary of one simulation run (Priority: P1) 🎯 MVP

**Goal**: Given a completed `SimulationRun`, produce a single `SummaryStatistics` — success rate, ending balance, percentile bands, median depletion age, median lifetime tax paid, and the unverified figures behind it.

**Independent Test**: Feed one completed `SimulationRun` into `summarize_run()` and confirm every field matches hand-computed values for that same run, without needing comparison support or export support to exist yet.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T011

- [X] T005 [P] [US1] Unit test `summarize_run()`'s `success_rate` and `percentile_bands` match the input run's own fields exactly (Acceptance Scenario US1.1) in `tests/unit/reporting/test_aggregation.py`
- [X] T006 [US1] Unit test `summarize_run()`'s `median_depletion_age` is computed only from paths whose `outcome.first_shortfall_plan_year is not None`, via `deemed_rmd_owner()`/`member_age_in_tax_year()` (Acceptance Scenario US1.2) in `tests/unit/reporting/test_aggregation.py`
- [X] T007 [US1] Unit test `summarize_run()`'s `median_depletion_age` is `None` — never `0` or a placeholder — when no path in the run ever depletes (Acceptance Scenario US1.3, Edge Cases) in `tests/unit/reporting/test_aggregation.py`
- [X] T008 [US1] Unit test `summarize_run()`'s `median_lifetime_tax_paid` is the median `cumulative_tax_paid` across every path, including depleted ones (Acceptance Scenario US1.4) in `tests/unit/reporting/test_aggregation.py`
- [X] T009 [US1] Unit test `summarize_run()` called twice on the identical run produces identical results (Acceptance Scenario US1.5, FR-013) in `tests/unit/reporting/test_aggregation.py`
- [X] T010 [P] [US1] Integration test: run quickstart.md §1 (summarize one simulation run) in `tests/integration/test_reporting_lifecycle.py`

### Implementation for User Story 1

- [X] T011 [US1] Implement `summarize_run()` in `src/retirement_planner/reporting/aggregation.py` — reads `run.success_rate`/`run.percentile_bands` directly, derives `ending_balance` from the final plan year's median percentile, `median_depletion_age`/`median_lifetime_tax_paid` by iterating `run.path_results`, and `unverified_figure_names` deduplicated by name from `run.figures_used` (FR-001–FR-004, research.md §1, §3, §5) (depends on T002, T003, T005–T009)
- [X] T012 [US1] Add `summarize_run` to `src/retirement_planner/reporting/__init__.py` exports (depends on T011)

**Checkpoint**: User Story 1 is independently functional — a single run can be summarized and inspected. No comparison support (US2) or export support (US3) yet.

---

## Phase 4: User Story 2 - Compare candidates using the same summary shape (Priority: P2)

**Goal**: Given a `SimulationComparisonResult` (`005`) or a deterministic `ComparisonResult` (`004`), produce one `SummaryStatistics` per candidate, in the candidates' own order.

**Independent Test**: Feed a `SimulationComparisonResult` with several candidates into `summarize_simulation_comparison()` and confirm the result contains one summary per candidate, each identical to what `summarize_run()` would produce for that candidate alone.

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] Unit test `summarize_simulation_comparison()` returns one summary per candidate, in input order, each identical to calling `summarize_run()` on that candidate directly (Acceptance Scenario US2.1) in `tests/unit/reporting/test_aggregation.py`
- [X] T014 [US2] Unit test `summarize_deterministic_comparison()` leaves `success_rate`/`percentile_bands` `None` while reporting `ending_balance` from `PlanOutcome.ending_balance` and `median_lifetime_tax_paid` from `PlanOutcome.cumulative_tax_paid` (Acceptance Scenario US2.2) in `tests/unit/reporting/test_aggregation.py`
- [X] T015 [US2] Unit test both comparison-summarization functions accept a single-candidate comparison and still return a valid one-entry list (Acceptance Scenario US2.3, mirroring `004`'s FR-011 and `005`'s FR-010 precedent) in `tests/unit/reporting/test_aggregation.py`
- [X] T016 [P] [US2] Integration test: run quickstart.md §2 (compare candidates, both Monte Carlo and deterministic) in `tests/integration/test_reporting_lifecycle.py`

### Implementation for User Story 2

- [X] T017 [US2] Implement `summarize_simulation_comparison()` in `src/retirement_planner/reporting/aggregation.py` — loops `summarize_run()` once per entry in `comparison.runs`, setting `candidate_label` from each run's own label (FR-005, research.md §4) (depends on T011)
- [X] T018 [US2] Implement `summarize_deterministic_comparison()` (and its private per-candidate helper) in `src/retirement_planner/reporting/aggregation.py` — loops `comparison.projections`, reading each `PlanOutcome`/`years[*].figures_used` directly and leaving Monte-Carlo-only fields `None` (FR-006, research.md §2, §4) (depends on T002, T003)
- [X] T019 [US2] Add `summarize_simulation_comparison` and `summarize_deterministic_comparison` to `src/retirement_planner/reporting/__init__.py` exports (depends on T017, T018)

**Checkpoint**: User Stories 1–2 are functional — single-run and comparison summaries both work. No export support (US3) yet.

---

## Phase 5: User Story 3 - Export a run or comparison as a spreadsheet-ready report (Priority: P3)

**Goal**: Render a `SimulationRun` as one CSV row per plan year, and a comparison result (either kind) as one CSV row per candidate — both spreadsheet/markdown-pipe-table ready.

**Independent Test**: Feed a `SimulationRun` into `run_to_csv_text()` and confirm the output is a header row plus one data row per plan year, with every value traceable back to the run's own `percentile_bands`.

### Tests for User Story 3 ⚠️

- [X] T020 [P] [US3] Unit test `run_to_csv_text()` produces a header row plus one data row per plan year, with percentile columns matching `run.percentile_bands` (Acceptance Scenario US3.1) in `tests/unit/reporting/test_export.py`
- [X] T021 [US3] Unit test `simulation_comparison_to_csv_text()` and `deterministic_comparison_to_csv_text()` each produce one row per candidate, clearly labeled by `candidate_label` (Acceptance Scenario US3.2) in `tests/unit/reporting/test_export.py`
- [X] T022 [US3] Unit test every export includes a `has_unverified_figure` column, `true` exactly when the underlying row/candidate involved an unverified figure (Acceptance Scenario US3.3) in `tests/unit/reporting/test_export.py`
- [X] T023 [P] [US3] Integration test: run quickstart.md §3 (CSV export for a run and a comparison) in `tests/integration/test_reporting_lifecycle.py`

### Implementation for User Story 3

- [X] T024 [US3] Implement `run_to_csv_text()` in `src/retirement_planner/reporting/export.py` — one row per plan year via `csv.DictWriter`/`io.StringIO`, percentile columns from `run.percentile_bands`, `has_unverified_figure` derived from `run.path_results[0].years[y].figures_used` (FR-008, FR-010, FR-012, research.md §6–7) (depends on T002, T003)
- [X] T025 [US3] Implement `simulation_comparison_to_csv_text()` and `deterministic_comparison_to_csv_text()` in `src/retirement_planner/reporting/export.py` — each calls the corresponding `summarize_*_comparison()` and renders one row per resulting `SummaryStatistics` (FR-009, FR-010, FR-012, research.md §7) (depends on T017, T018)
- [X] T026 [US3] Add `run_to_csv_text`, `simulation_comparison_to_csv_text`, `deterministic_comparison_to_csv_text` to `src/retirement_planner/reporting/__init__.py` exports (depends on T024, T025)

**Checkpoint**: User Stories 1–3 are functional — summarization and export both work for single runs and comparisons of either kind. No dedicated verification pass (US4) yet.

---

## Phase 6: User Story 4 - See which figures are still unverified, prominently (Priority: P4)

**Goal**: Confirm — with a dedicated test pass, not new production code — that every unverified figure behind a run or comparison is visibly represented in both the summary (User Story 1) and the export (User Story 3), never merely by its absence from a "verified" list.

**Independent Test**: Feed a `SimulationRun` known to include at least one unverified figure (`005`'s historical-bootstrap paths always carry one) into `summarize_run()` and `run_to_csv_text()`, and confirm the unverified figure is named explicitly and completely in both outputs.

### Tests for User Story 4 ⚠️

> No new implementation tasks in this phase — `summarize_run()` (T011) and the exporters (T024–T025) already implement `unverified_figure_names`/`has_unverified_figure` as part of their Functional Requirements (FR-004, FR-010); this phase is verification only.

- [X] T027 [P] [US4] Unit test `summarize_run()`'s `unverified_figure_names` includes every distinct unverified figure and excludes every verified one, using a run built from `005`'s historical-bootstrap paths (Acceptance Scenario US4.1) in `tests/unit/reporting/test_aggregation.py` — **note**: implemented against hand-built `FigureUsage` fixtures rather than literal `005` historical-bootstrap paths (equivalent coverage, simpler/faster); the integration test (T029) exercises the real historical-bootstrap path as specified
- [X] T028 [US4] Unit test `summarize_run()`'s `unverified_figure_names` is present and empty — not omitted — for a run whose `figures_used` contains no unverified entries (Acceptance Scenario US4.2) in `tests/unit/reporting/test_aggregation.py`
- [X] T029 [P] [US4] Integration test: run quickstart.md §4 (unverified figures surfaced in both summary and export) in `tests/integration/test_reporting_lifecycle.py`

**Checkpoint**: All four user stories are independently functional — single-run summaries, comparison summaries (both kinds), CSV export, and unverified-figure surfacing all work correctly, per [quickstart.md](./quickstart.md) steps 1–4.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify this feature's cross-cutting requirements (deduplication correctness, performance) and tie the quickstart walkthrough together as one acceptance run

- [X] T030 [P] Unit test the unverified-figure deduplication-by-name logic against a constructed case with two `FigureUsage` entries sharing one `name` but different `last_verified` dates, confirming a single collapsed entry in the result (research.md §5, Edge Cases) in `tests/unit/reporting/test_aggregation.py` (depends on T011)
- [X] T031 Run the complete [quickstart.md](./quickstart.md) walkthrough (all 4 sections) as one end-to-end assertion sequence in `tests/integration/test_reporting_lifecycle.py` (depends on T010, T016, T023, T029)
- [X] T032 [P] Add docstrings to every public function/dataclass in `src/retirement_planner/reporting/{models,aggregation,export}.py` referencing the corresponding section of [contracts/reporting-api.md](./contracts/reporting-api.md) (depends on T012, T019, T026)
- [X] T033 [P] Add a lightweight timing check confirming `summarize_run()` and `run_to_csv_text()` on a 5,000-path reference-scale run each complete with no perceptible added delay beyond the simulation itself (plan.md Performance Goals, SC-005) in `tests/integration/test_reporting_performance.py` (depends on T011, T024) — **PASSED: 3.64s total (run generation + simulation + summarize + export)**, well under budget

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational **and** User Story 1's `summarize_run()` (T011) for its `summarize_simulation_comparison()` half; its `summarize_deterministic_comparison()` half depends only on Foundational
- **User Story 3 (Phase 5)**: Depends on Foundational for `run_to_csv_text()` (T024); depends on User Story 2's both comparison functions (T017, T018) for its two comparison exporters (T025)
- **User Story 4 (Phase 6)**: Depends on User Story 1's `summarize_run()` (T011) and User Story 3's `run_to_csv_text()` (T024) — it verifies their existing behavior, adding no new implementation
- **Polish (Phase 7)**: `T030` depends on US1 (`T011`); `T031` depends on all four user stories' integration tests; `T032`/`T033` depend on every story's exports

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — the MVP slice, and the base every other story reuses
- **User Story 2 (P2)**: Depends on US1's `summarize_run()` existing (for the Monte Carlo half only); no dependency on US3 or US4
- **User Story 3 (P3)**: Depends on US2's both comparison-summarization functions (for its comparison exporters); its single-run exporter depends only on Foundational, not on US1 or US2
- **User Story 4 (P4)**: Depends on US1 and US3 both existing — it is a verification-only pass over their behavior
- Unlike `001`–`003`'s fully independent stories, this feature's stories are **sequential by construction** (US2 reuses US1, US3 reuses US2, US4 verifies US1+US3) — there is no meaningful "build US2/US3/US4 in parallel" opportunity the way `004`'s US2/US3/US4 had

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task
- Foundational's renamed helpers (T002) and `SummaryStatistics` (T003) before any story-specific code
- Within US2: `summarize_simulation_comparison()` (T017, needs T011) and `summarize_deterministic_comparison()` (T018, needs only Foundational) have no dependency on each other and can be built in parallel
- Within US3: `run_to_csv_text()` (T024, needs only Foundational) and the two comparison exporters (T025, needs T017/T018) have no dependency on each other and can be built in parallel

### Parallel Opportunities

- T002 (`comparison/projection.py` rename) and T003 (`reporting/models.py`) can start together once T001 is done — different files, no shared dependency
- T005 (US1's first test) and T013/T014 (US2's tests, once US1's implementation lands) target different concerns in the same eventual file (`test_aggregation.py`) — sequential within that file, but T020 (US3's `test_export.py`, a different file) can proceed in parallel with any US1/US2 test once its own dependencies (T024) are ready
- Within US2: T017 and T018 can be implemented in parallel (different functions, same file — coordinate on merge order within `aggregation.py`)
- Within US3: T024 and T025 can be implemented in parallel (different functions, same file — coordinate on merge order within `export.py`)
- T032 (docstrings) and T033 (performance check) can run in parallel — separate files

---

## Parallel Example: User Story 2's two comparison functions

```bash
# Launch both halves of User Story 2 together (different functions, same file,
# one depends on US1's summarize_run(), the other only on Foundational):
Task: "Implement summarize_simulation_comparison() in src/retirement_planner/reporting/aggregation.py"
Task: "Implement summarize_deterministic_comparison() in src/retirement_planner/reporting/aggregation.py"
```

(Note: both land in the shared `aggregation.py` file per plan.md's Project Structure — genuinely parallel authorship will need coordination or sequential merging even though the *logic* has no cross-dependency.)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest tests/unit/reporting/test_aggregation.py tests/integration/test_reporting_lifecycle.py` and confirm SC-001 holds
5. This alone proves the core aggregation engine — every comparison summary and CSV export this feature offers is this same `summarize_run()` reused or rendered

### Incremental Delivery

1. Setup + Foundational → foundation ready (the `004` age-translation reuse is live)
2. Add User Story 1 → single-run summarization → validate independently (SC-001) → this is the MVP
3. Add User Story 2 → comparison summaries (both kinds) → validate independently (SC-002)
4. Add User Story 3 → CSV export → validate independently (SC-003)
5. Add User Story 4 → dedicated unverified-figure verification pass → validate independently (SC-004)
6. Polish → deduplication edge case, full quickstart.md walkthrough, docstrings, performance check (SC-005)

### Suggested Team Split

User Story 1 must land first and cannot be usefully parallelized across contributors (`summarize_run()` is one small aggregation function every later story reuses). Once it's merged: User Story 2's two comparison functions (T017, T018) can be split across two contributors (they don't depend on each other); once both land, User Story 3's two exporter groups (T024, T025) can likewise be split. User Story 4 is best done by whoever is free last, since it only verifies already-merged behavior — it has no implementation to parallelize.
