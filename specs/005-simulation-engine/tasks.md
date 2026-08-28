---

description: "Task list for Simulation Engine"
---

# Tasks: Simulation Engine

**Input**: Design documents from `/specs/005-simulation-engine/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/simulation-api.md](./contracts/simulation-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Project Structure and the constitution's Development Workflow gate ("unit test coverage for numeric primitives") both specify test files as deliverables of this feature, matching the precedent set by `001`–`004`. This feature additionally carries a **mandatory** performance benchmark task (T051) — plan.md's Constitution Check leaves Principle VI (Performance Budget) as an open risk-with-mitigation rather than a settled PASS, explicitly stating this feature "is not considered complete until that benchmark passes."

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P5) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- File paths are exact and relative to the repository root

## Path Conventions

Single Python library project, `src/` layout, per [plan.md](./plan.md) Project Structure:
- Library code: `src/retirement_planner/simulation/`, plus one additive change to `src/retirement_planner/comparison/{models,projection}.py`
- Tests: `tests/unit/simulation/`, `tests/unit/comparison/`, `tests/integration/`

No new runtime dependencies (plan.md Technical Context) — `pyproject.toml` is unchanged; `numpy` was considered and rejected (research.md §6). This feature imports from `retirement_planner.scenario`, `retirement_planner.tax`, `retirement_planner.mechanics`, and `retirement_planner.comparison`; only `comparison/models.py` and `comparison/projection.py` change outside this feature's own subpackage (research.md §1) — no other file in `001`–`004` changes.

**This feature's stories are NOT mutually independent**, mirroring `004`'s own note: **User Story 1 is the hard prerequisite for every other story.** `compare_*()` (US2) all loop `run_simulation()` (US1); demonstrating US4's timing-sensitivity acceptance scenario and all of US5's scoring both call `run_simulation()` directly. US3's return-generation function (`generate_historical_bootstrap_paths()`) and US4's `apply_stress_scenario()` need only the Foundational phase to exist as standalone functions, but US3's mode-mismatch validation (FR-011) is added to the `compare_*()` functions US2 builds, so US3's full scope depends on US2 as well as Foundational. Once US1 (and, for US3, US2) exist, US3, US4, and US5 have no dependency on each other and can proceed in parallel.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create the simulation subpackage directory skeleton: `src/retirement_planner/simulation/__init__.py`, `tests/unit/simulation/__init__.py` (mirrors `004`'s `comparison/` layout; `tests/integration/` already exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `ReturnSchedule` seam into `004`'s existing projection loop, and every shared data shape this feature's five stories build on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Add the `ReturnSchedule` protocol and `DeterministicReturnAssumption.return_for_plan_year()` to `src/retirement_planner/comparison/models.py` — additive only; the existing `annual_real_return` field and every other `004` type is untouched (research.md §1)
- [X] T003 [P] Define all shared simulation data types in `src/retirement_planner/simulation/models.py`: `GenerationMode`, `ReturnPath`, `StressScenario`, `SurvivalCurve`, `PercentileBand`, `ComparisonAxis`, `SimulationRun`, `SimulationComparisonResult` — importing `StrategyConfiguration`, `PlanProjection` from `retirement_planner.comparison` and `FigureUsage` from `retirement_planner.tax` rather than redefining them, exactly matching [data-model.md](./data-model.md) and [contracts/simulation-api.md](./contracts/simulation-api.md)
- [X] T004 Unit test: `run_plan_projection()`'s growth-factor line calls `return_assumption.return_for_plan_year(plan_year)` rather than reading `.annual_real_return` directly — confirm a year-varying stub `ReturnSchedule` produces year-varying growth between plan years, and confirm every existing `004` test constructing a bare `DeterministicReturnAssumption` still passes unmodified (research.md §1) in `tests/unit/comparison/test_projection.py` (depends on T002, T003) — write FIRST, ensure it FAILS before T005
- [X] T005 Update `run_plan_projection()`'s growth-factor line and `return_assumption` parameter's type hint in `src/retirement_planner/comparison/projection.py` (research.md §1) (depends on T004)
- [X] T006 Wire base exports in `src/retirement_planner/simulation/__init__.py` — re-export every type from T003 (function exports are added per story below) (depends on T003, T005)

**Checkpoint**: Foundation ready — User Story 1 implementation can now begin

---

## Phase 3: User Story 1 - Run a probabilistic Monte Carlo simulation for one configuration (Priority: P1) 🎯 MVP

**Goal**: Given a scenario and one strategy configuration, generate many independent randomly-drawn return paths and run `run_plan_projection()` once per path, aggregating the results into a success rate and percentile ending-balance bands.

**Independent Test**: Feed one complete scenario, configuration, path count, and seed into `generate_return_paths()` then `run_simulation()`, and confirm the result contains one `PlanProjection` per path plus a correctly-derived `success_rate` and `percentile_bands`, reproducible under a repeat call.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T016–T018

- [X] T007 [P] [US1] Unit test `generate_return_paths()`'s correlated-normal draw formula against hand-computed reference draws for a fixed seed — confirms the fixed RNG consumption order (path, then year, then `z1` before `z2`) and the Cholesky transform (research.md §3) in `tests/unit/simulation/test_returns.py`
- [X] T008 [US1] Unit test `generate_return_paths()` raises `ValueError` for `path_count <= 0` (FR-006, Acceptance Scenario US1.5) in `tests/unit/simulation/test_returns.py`
- [X] T009 [US1] Unit test `generate_return_paths()` called twice with identical `market_assumptions`/`path_count`/`horizon_years`/`seed` returns identical `ReturnPath`s (FR-005, Acceptance Scenario US1.3) in `tests/unit/simulation/test_returns.py`
- [X] T010 [P] [US1] Unit test `run_simulation()` computes `success_rate` as the share of `path_results` whose `outcome.first_shortfall_plan_year is None` (FR-003, Acceptance Scenario US1.2) in `tests/unit/simulation/test_monte_carlo.py`
- [X] T011 [US1] Unit test `run_simulation()` retains each depleted path's own `first_shortfall_plan_year` individually within `path_results`, never dropping or smoothing it into the aggregate (FR-004, Acceptance Scenario US1.4) in `tests/unit/simulation/test_monte_carlo.py`
- [X] T012 [US1] Unit test `run_simulation()`'s `percentile_bands` contains one entry per plan year, each `percentiles` dict computed from `path_results`' ending balances for that year (implemented via a stdlib linear-interpolation helper rather than `statistics.quantiles`, research.md §6) (FR-003, Acceptance Scenario US1.1) in `tests/unit/simulation/test_monte_carlo.py`
- [X] T013 [US1] Unit test `run_simulation()` raises `ValueError` for an empty `return_paths` list (FR-006, Acceptance Scenario US1.5) in `tests/unit/simulation/test_monte_carlo.py`
- [X] T014 [US1] Unit test `run_simulation()` called twice with identical scenario, configuration, and `return_paths` produces identical `success_rate` and `percentile_bands`, including when path-level dispatch is forced through the parallel code path (FR-005, Acceptance Scenario US1.3, Principle II) in `tests/unit/simulation/test_monte_carlo.py`
- [X] T015 [P] [US1] Integration test: run quickstart.md §1 (probabilistic simulation, percentile bands, reproducibility) in `tests/integration/test_simulation_lifecycle.py`

### Implementation for User Story 1

- [X] T016 [US1] Implement `generate_return_paths()` in `src/retirement_planner/simulation/returns.py` — the correlated-normal transform, consuming `random.Random(seed)` in the fixed order T007 tests (research.md §3, FR-001) (depends on T003, T007–T009)
- [X] T017 [US1] Implement `run_simulation()` in `src/retirement_planner/simulation/monte_carlo.py` — loops `run_plan_projection()` once per `ReturnPath`, aggregates `success_rate`/`percentile_bands`/deduplicated `figures_used` (FR-002–FR-004, FR-019), dispatching path-level work through `concurrent.futures.ProcessPoolExecutor` once `path_count` exceeds an implementation-chosen threshold (research.md §7) (depends on T005, T016, T010–T014)
- [X] T018 [US1] Add `generate_return_paths` and `run_simulation` to `src/retirement_planner/simulation/__init__.py` exports (depends on T016, T017)

**Checkpoint**: User Story 1 is independently functional — a probabilistic Monte Carlo simulation can be run and inspected for one configuration. No comparison across candidates (US2), historical bootstrap (US3), stress scenarios (US4), or survival adjustment (US5) yet.

---

## Phase 4: User Story 2 - Compare configurations, including states, using paired random draws (Priority: P2)

**Goal**: Run `run_simulation()` once per candidate configuration — states, Roth conversion strategies, withdrawal orders, or claiming-age pairs — reusing the identical pre-generated `list[ReturnPath]` across every candidate, so any outcome difference is attributable only to the compared dimension.

**Independent Test**: Feed one scenario, a shared `return_paths` list, and two or more states into `compare_states()`, and confirm every candidate's `path_results[i]` was produced from the identical `return_paths[i]` object, assembled into one `SimulationComparisonResult`.

### Tests for User Story 2 ⚠️

- [X] T019 [P] [US2] Unit test `compare_states()` returns one `SimulationRun` per state, every run's `path_results[i].return_assumption is return_paths[i]` (structural pairing, FR-007, FR-009, Acceptance Scenarios US2.1/US2.3) in `tests/unit/simulation/test_compare.py`
- [X] T020 [US2] Unit test `compare_states()` produces equal `success_rate` and `percentile_bands` for two states that are financially identical for a fixture scenario, never introducing a spurious paired-draw difference (Acceptance Scenario US2.4) in `tests/unit/simulation/test_compare.py`
- [X] T021 [US2] Unit test `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, and `compare_claiming_age_grid()` each reuse the identical `return_paths` list across every candidate, mirroring `compare_states()` (Acceptance Scenario US2.2) in `tests/unit/simulation/test_compare.py`
- [X] T022 [US2] Unit test all four `compare_*()` functions accept a single-candidate list and still return a valid one-entry `SimulationComparisonResult` (Acceptance Scenario US2.5, FR-010, mirroring `004`'s FR-011 precedent) in `tests/unit/simulation/test_compare.py`
- [X] T023 [P] [US2] Integration test: run quickstart.md §2 (state comparison via a shared Paired-Draw Set) in `tests/integration/test_simulation_lifecycle.py` — **note**: under the parallel-dispatch threshold this must assert value equality (`==`), not object identity (`is`), since a worker-process round trip deserializes a copy; the identity-level guarantee is exercised by T019's below-threshold unit test instead (finding surfaced during implementation)

### Implementation for User Story 2

- [X] T024 [US2] Implement `compare_states()` in `src/retirement_planner/simulation/compare.py` — loops `run_simulation()` once per state in `states`, holding `strategy`/`return_paths`/every other input fixed (FR-007, FR-009, research.md §2) (depends on T017)
- [X] T025 [US2] Implement `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, and `compare_claiming_age_grid()` in `src/retirement_planner/simulation/compare.py` — mirror `004`'s `compare.py` candidate-forcing pattern (`dataclasses.replace`), substituting `return_paths` for `return_assumption` and looping `run_simulation()` instead of `run_plan_projection()` (FR-008, FR-009) (depends on T017)
- [X] T026 [US2] Add `compare_states`, `compare_roth_conversion_strategies`, `compare_withdrawal_sequencing_strategies`, `compare_claiming_age_grid` to `src/retirement_planner/simulation/__init__.py` exports (depends on T024, T025)

**Checkpoint**: User Stories 1–2 are functional — probabilistic single-configuration simulation and paired-draw comparison across all four axes (including the new state axis) both work. No historical bootstrap (US3), stress scenarios (US4), or survival adjustment (US5) yet.

---

## Phase 5: User Story 3 - Generate returns from resampled historical history instead of a parametric distribution (Priority: P3)

**Goal**: Add an alternative return-generation mode that builds each path from contiguous, randomly-selected blocks of a documented historical annual-return series, consumable by the identical `run_simulation()`/`compare_*()` aggregation logic as parametric-mode paths.

**Independent Test**: Call `generate_historical_bootstrap_paths()` with a path count, horizon, seed, and block length, and confirm each path's returns are built from contiguous historical blocks, are reproducible under a fixed seed, and feed into `run_simulation()` without any change to that function's own logic.

### Tests for User Story 3 ⚠️

- [X] T027 [P] [US3] Unit test `generate_historical_bootstrap_paths()` builds each path's `annual_returns` from contiguous `block_length`-year blocks drawn from `HISTORICAL_RETURNS.schedule`, not independently-resampled individual years (Acceptance Scenario US3.1) in `tests/unit/simulation/test_returns.py`
- [X] T028 [US3] Unit test `generate_historical_bootstrap_paths()` called twice with identical parameters and seed returns identical resampled `ReturnPath`s (Acceptance Scenario US3.2) in `tests/unit/simulation/test_returns.py`
- [X] T029 [US3] Unit test `generate_historical_bootstrap_paths()` raises `ValueError` when `block_length` exceeds the number of documented historical years, or is `<= 0` (Acceptance Scenario US3.4, FR-013) in `tests/unit/simulation/test_returns.py`
- [X] T030 [US3] Unit test every `compare_*()` function raises `ValueError` when a caller attempts to combine `return_paths` of different `generation_mode`s within one comparison (Acceptance Scenario US3.3, FR-011, Edge Cases) in `tests/unit/simulation/test_compare.py`
- [X] T031 [P] [US3] Integration test: run quickstart.md §3 (historical-bootstrap paths consumed by `run_simulation()`) in `tests/integration/test_simulation_lifecycle.py`

### Implementation for User Story 3

- [X] T032 [P] [US3] Define `HISTORICAL_RETURNS: SourcedFigure[tuple[float, float]]` in `src/retirement_planner/simulation/historical_data.py` — **note**: generated as clearly-labeled *synthetic* placeholder data (a fixed local seed, independent of caller seeds), since no network access is available to source a real series even at authoring time (Principle V); `verified=False` pending a primary source (research.md §4) (depends on T003)
- [X] T033 [US3] Implement `generate_historical_bootstrap_paths()` in `src/retirement_planner/simulation/returns.py` — moving-block bootstrap over `HISTORICAL_RETURNS.schedule`, attaching `HISTORICAL_RETURNS.usage_for_year()` into each path's `figures_used` for every historical year drawn (FR-012, FR-013, research.md §4) — **note**: contracts/simulation-api.md and quickstart.md were corrected during implementation to add a `market_assumptions: MarketAssumptions` parameter (allocation weights only), which the original planning docs had omitted despite the blending step requiring it (depends on T032, T016, T027–T029)
- [X] T034 [US3] Add the `generation_mode` mismatch validation to `compare.py`'s shared candidate-dispatch logic (FR-011) (depends on T024, T025, T030)
- [X] T035 [US3] Add `generate_historical_bootstrap_paths` and `HISTORICAL_RETURNS` to `src/retirement_planner/simulation/__init__.py` exports (depends on T033)

**Checkpoint**: User Stories 1–3 are functional — parametric and historical-bootstrap return generation both feed the same simulation and comparison machinery. No stress scenarios (US4) or survival adjustment (US5) yet.

---

## Phase 6: User Story 4 - Apply a configurable sequence-of-returns stress scenario (Priority: P4)

**Goal**: Override a configurable, contiguous window of every path's returns to a fixed shock magnitude, leaving every other plan year — and every non-return mechanic — unaffected, and demonstrate that the shock's timing (not only its magnitude) changes outcomes.

**Independent Test**: Apply `apply_stress_scenario()` to an already-generated `list[ReturnPath]` and confirm the configured window is overridden while other years are untouched; run `run_simulation()` on two stress-tested path sets differing only in the shock's starting plan year and confirm their outcomes are free to differ.

### Tests for User Story 4 ⚠️

- [X] T036 [P] [US4] Unit test `apply_stress_scenario()` overrides only the configured window's `annual_returns` to `magnitude`, leaving every other plan year, `generation_mode`, and `figures_used` unchanged (Acceptance Scenario US4.1) in `tests/unit/simulation/test_returns.py`
- [X] T037 [US4] Unit test two stress scenarios identical except for `start_plan_year` produce different `run_simulation()` success rates when applied to the same base paths (Acceptance Scenario US4.2, sequence-of-returns risk) in `tests/unit/simulation/test_returns.py`
- [X] T038 [US4] Unit test `apply_stress_scenario()` raises `ValueError` when `start_plan_year + duration_years - 1` exceeds `horizon_last_plan_year` (Acceptance Scenario US4.3, FR-015) in `tests/unit/simulation/test_returns.py`
- [X] T039 [US4] Unit test a stress-tested Paired-Draw Set passed into a `compare_*()` call applies the identical shock window and magnitude to every candidate (Acceptance Scenario US4.4, FR-016) in `tests/unit/simulation/test_compare.py`
- [X] T040 [P] [US4] Integration test: run quickstart.md §4 (configurable stress scenario, timing sensitivity) in `tests/integration/test_simulation_lifecycle.py`

### Implementation for User Story 4

- [X] T041 [US4] Implement `apply_stress_scenario()` in `src/retirement_planner/simulation/returns.py` — non-mutating window override via `dataclasses.replace` (FR-014, FR-015) (depends on T003, T036–T038)
- [X] T042 [US4] Add `apply_stress_scenario` to `src/retirement_planner/simulation/__init__.py` exports (depends on T041)

**Checkpoint**: User Stories 1–4 are functional. No survival adjustment (US5) yet.

---

## Phase 7: User Story 5 - Express success as survival-adjusted probability instead of a fixed horizon (Priority: P5)

**Goal**: Add an optional, additive survival-adjusted success metric alongside the standard fixed-horizon success rate, using each household member's actuarial survival curve, without altering the standard metric.

**Independent Test**: Run `run_simulation()` twice on identical inputs — once with `survival_curves` supplied, once without — and confirm the fixed-horizon `success_rate` is identical in both, while only the first run reports a non-`None` `survival_adjusted_success_rate`.

### Tests for User Story 5 ⚠️

- [X] T043 [P] [US5] Unit test `run_simulation()` with `survival_curves` supplied reports a `survival_adjusted_success_rate` alongside an unaffected `success_rate`; the same call without `survival_curves` leaves `survival_adjusted_success_rate` as `None` (Acceptance Scenarios US5.1–US5.2, FR-017) in `tests/unit/simulation/test_survival.py`
- [X] T044 [US5] Unit test a path whose `first_shortfall_plan_year` occurs after both household members' `survival_probability(age) < 0.5` counts as a survival-adjusted success despite counting as a fixed-horizon failure (Acceptance Scenario US5.3) in `tests/unit/simulation/test_survival.py`
- [X] T045 [US5] Unit test `run_simulation()` raises `KeyError` when `survival_curves` is supplied but omits a household member's `person_name` (Acceptance Scenario US5.4, FR-018) in `tests/unit/simulation/test_survival.py`
- [X] T046 [P] [US5] Integration test: run quickstart.md §5 (survival-adjusted scoring alongside the standard success rate) in `tests/integration/test_simulation_lifecycle.py`

### Implementation for User Story 5

- [X] T047 [P] [US5] Define `SURVIVAL_TABLE: dict[str, SurvivalCurve]` in `src/retirement_planner/simulation/survival_data.py` — an illustrative per-role period life table, `verified=False` pending a primary source (research.md §5) (depends on T003)
- [X] T048 [US5] Implement survival-adjusted scoring in `run_simulation()` (`src/retirement_planner/simulation/monte_carlo.py`) — per-path, per-member threshold determination against `SurvivalCurve.survival_probability()` at the shortfall plan year, computed only when `survival_curves` is passed, and its `FigureUsage` added into `figures_used` when used (FR-017, FR-018, research.md §5) — implemented alongside T017 in anticipation of this story; T043–T045 confirmed it without further changes needed (depends on T017, T047, T043–T045)
- [X] T049 [US5] Add `SURVIVAL_TABLE` and `SurvivalCurve` to `src/retirement_planner/simulation/__init__.py` exports (depends on T047, T048)

**Checkpoint**: All five user stories are independently functional — probabilistic single-configuration simulation, paired-draw comparison across four axes, historical-bootstrap generation, configurable stress scenarios, and survival-adjusted scoring, per [quickstart.md](./quickstart.md) steps 1–5.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify this feature's cross-cutting requirements (figure deduplication, the mandatory performance budget) and tie the quickstart walkthrough together as one acceptance run

- [X] T050 [P] Unit test `SimulationRun.figures_used` deduplicates by `(name, last_verified)` across the thousands of per-path/per-year figure unions a run assembles (FR-019) in `tests/unit/simulation/test_monte_carlo.py` (depends on T017) — written alongside T010-T014 during US1
- [X] T051 **Mandatory performance benchmark** (plan.md Constitution Check's open Performance Budget gate, research.md §7, SC-003): assert a 5,000-path `run_simulation()` call and a 5,000-path × 3-state `compare_states()` call (every state currently registered in `002`'s `STATE_MODULES`) each complete in well under a minute on dev/CI hardware; tune the `ProcessPoolExecutor` dispatch threshold and chunk size empirically until the budget is met in `tests/integration/test_simulation_performance.py` (depends on T017, T024) — **PASSED: 3.77s total for both benchmarks** (60s budget). Empirical finding: per-plan-year mechanics/tax cost ~0.375ms, far below the ~50ms conservative estimate `004`'s plan.md used — serial dispatch alone meets budget with ~15x headroom at reference scale, and naive `ProcessPoolExecutor` dispatch at that per-task cost was measured *slower* than serial (IPC/pickling overhead dominates). Fixed via: (1) raising `_PARALLEL_DISPATCH_THRESHOLD` to 8,000 so the documented reference scale runs serially by default; (2) switching parallel dispatch (still implemented and correctness-tested above threshold, `tests/unit/simulation/test_monte_carlo.py`) to a `ProcessPoolExecutor(initializer=...)` pattern that sends shared arguments once per worker instead of once per path, plus a tuned `chunksize`. research.md §7 updated with this finding.
- [X] T052 Run the complete [quickstart.md](./quickstart.md) walkthrough (all 5 sections) as one end-to-end assertion sequence in `tests/integration/test_simulation_lifecycle.py` (depends on T015, T023, T031, T040, T046)
- [X] T053 [P] Add docstrings to every public function/dataclass in `src/retirement_planner/simulation/{models,returns,historical_data,survival_data,monte_carlo,compare}.py` referencing the corresponding section of [contracts/simulation-api.md](./contracts/simulation-api.md) (depends on T018, T026, T035, T042, T049)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational **and** User Story 1's `run_simulation()` (T017) — every `compare_*()` function loops it directly
- **User Story 3 (Phase 5)**: Depends on Foundational for its generator function (T016 for the shared `ReturnPath` shape); its FR-011 mode-mismatch validation (T034) depends on User Story 2's `compare_*()` functions (T024, T025) existing to add the check to
- **User Story 4 (Phase 6)**: Depends on Foundational only for `apply_stress_scenario()` itself (T003, T041); its timing-sensitivity acceptance test (T037) depends on User Story 1's `run_simulation()` (T017)
- **User Story 5 (Phase 7)**: Depends on Foundational and User Story 1's `run_simulation()` (T017), which its scoring logic (T048) extends directly
- **Polish (Phase 8)**: `T050`/`T051` depend on US1/US2 (`T017`, `T024`); `T052` depends on all five user stories' integration tests; `T053` depends on every story's exports

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — the MVP slice, and the only story every other one builds on
- **User Story 2 (P2)**: Depends on US1's `run_simulation()`; no dependency on US3, US4, or US5
- **User Story 3 (P3)**: Depends on Foundational directly for its own generator; depends on US2 only for the mode-mismatch validation (T034) — the generator itself (T016, T033) could be built alongside US2, but the full story (including T030/T034) is sequenced after US2 here for clarity
- **User Story 4 (P4)**: Depends on Foundational directly for `apply_stress_scenario()`; depends on US1 only for its own acceptance test (T037) demonstrating timing sensitivity through `run_simulation()` — no dependency on US2, US3, or US5
- **User Story 5 (P5)**: Depends on US1's `run_simulation()`, which it extends directly; no dependency on US2, US3, or US4
- Once US1 (and, for US3's full scope, US2) exist, **US3, US4, and US5 have no dependency on each other** and can proceed in parallel

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task
- Foundational's `ReturnSchedule` seam (T002, T004, T005) and shared types (T003) before any story-specific code
- Within US1: `generate_return_paths()` (T016) before `run_simulation()` (T017), which consumes its output
- Within US3: `HISTORICAL_RETURNS` (T032) before `generate_historical_bootstrap_paths()` (T033), which reads it
- Within US5: `SURVIVAL_TABLE`/`SurvivalCurve` (T047) before the scoring logic that consults it (T048)

### Parallel Opportunities

- T002 (`comparison/models.py`) and T003 (`simulation/models.py`) can start together once T001 is done — different files, and T003's `ReturnPath.return_for_plan_year()` only needs the *shape* of the protocol T002 defines, not its implementation
- T007 (US1's return-generation test, new file) and T010 (US1's aggregation test, a different new file) can start in parallel once Foundational is done
- **User Story 4's `apply_stress_scenario()` (T041) and User Story 5's `SURVIVAL_TABLE` (T047) can be built fully in parallel** by different contributors once Foundational and US1 are done, since neither depends on the other or on US2/US3
- T053 (docstrings) can run alongside T050/T051/T052 once every story's exports land — different concern, same phase

---

## Parallel Example: User Stories 4 and 5 (post-US1/US2)

```bash
# Launch each story's first test in two different new files:
Task: "Unit test apply_stress_scenario() window override in tests/unit/simulation/test_returns.py"
Task: "Unit test run_simulation() survival-adjusted scoring in tests/unit/simulation/test_survival.py"

# Launch each story's implementation task together (neither imports the other's code):
Task: "Implement apply_stress_scenario() in src/retirement_planner/simulation/returns.py"
Task: "Define SURVIVAL_TABLE in src/retirement_planner/simulation/survival_data.py"
```

(Note: US4's `apply_stress_scenario()` lands in `returns.py` alongside US1's `generate_return_paths()` and US3's `generate_historical_bootstrap_paths()` — genuinely parallel authorship of that file across stories will need coordination or sequential merging even though the *logic* has no cross-dependency.)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest tests/unit/simulation/test_returns.py tests/unit/simulation/test_monte_carlo.py tests/integration/test_simulation_lifecycle.py` and confirm SC-001 holds
5. This alone proves the multi-path Monte Carlo core — every comparison, alternative return mode, stress scenario, and survival adjustment this feature offers builds on this same `run_simulation()` call

### Incremental Delivery

1. Setup + Foundational → foundation ready (the `ReturnSchedule` seam into `004` is live)
2. Add User Story 1 → probabilistic single-configuration simulation → validate independently (SC-001) → this is the MVP
3. Add User Story 2 → paired-draw comparison across states/strategies/orders/claiming-ages → validate independently (SC-002)
4. Add User Story 3 → historical-bootstrap return generation → validate independently (SC-005)
5. Add User Story 4 → configurable stress scenarios → validate independently (SC-006)
6. Add User Story 5 → survival-adjusted success metric → validate independently (SC-007)
7. Polish → figure deduplication, **mandatory performance benchmark (T051)**, full quickstart.md walkthrough, docstrings (SC-003, SC-004)

### Suggested Team Split

User Story 1 must land first and cannot be meaningfully parallelized across contributors (`run_simulation()` is one aggregation function consumed by everything downstream). Once `run_simulation()` (T017) is merged: User Story 2 can proceed alone (it's the direct consumer every comparison axis needs); once User Story 2's `compare_*()` functions also exist, User Story 3, User Story 4, and User Story 5 can be built fully in parallel by three different contributors — each touches a distinct file (`historical_data.py`, the stress-override portion of `returns.py`, `survival_data.py` plus a scoring addition to `monte_carlo.py`) with no cross-story import dependency, though US3's and US4's functions land in the shared `returns.py` file (see the Parallel Example note above) and should coordinate on merge order.
