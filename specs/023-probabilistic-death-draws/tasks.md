---

description: "Task list for 023-probabilistic-death-draws"
---

# Tasks: Monte Carlo Per-Path Probabilistic Death Draws

**Input**: Design documents from `/specs/023-probabilistic-death-draws/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The constitution's "Unit test coverage for numeric primitives" gate
(Development Workflow & Quality Gates) and this project's existing precedent (016-018, 020-022)
require new engine behavior to have unit tests against hand-calculated/reference values before
it's used in any comparative run.

**Organization**: Tasks are grouped by user story (spec.md) to enable independent implementation
and testing of each story. Per the pre-decided scope (spec.md Assumptions), there is no BFF/UI
polish phase this time — this feature is core-library only.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project — `src/retirement_planner/simulation/`, `tests/` at repo root (see plan.md Project
Structure). No `services/bff/` or `apps/streamlit_ui/` changes in this feature.

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before changing shared code.

- [X] T001 Run `pytest tests/` and confirm the existing suite is green before any change in this feature (baseline for regression comparison later)

**Checkpoint**: Baseline confirmed green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The draw-generation primitive every later phase depends on — `generate_death_age_draws()`
and its own conditional-sampling math (research.md §1, §4, §5) — has no dependents *of* it within
this feature, so it must exist first.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Create `src/retirement_planner/simulation/mortality.py` with a module docstring (mirroring `returns.py`'s own role-description convention) and a private `_draw_death_age(curve: SurvivalCurve, current_age: int, rng: random.Random) -> int | None`: computes `reference_survival` per the three boundary rules in data-model.md § Derived (`current_age <= 50` → `1.0`; `current_age > 110` → `curve.probabilities_by_age[110]`; otherwise a direct lookup), draws `V = rng.random()`, and returns the smallest documented age `a >= current_age` with `curve.probabilities_by_age[a] <= reference_survival * V`, or `None` if none exists (research.md §4)
- [X] T003 Add `generate_death_age_draws(household: Household, survival_curves: dict[str, SurvivalCurve], path_count: int, seed: int) -> list[dict[str, int | None]]` to the same module: raises `ValueError` if `path_count <= 0`; raises `KeyError` if any `household.members[*].person_name` is missing from `survival_curves`; builds one `random.Random(seed)` instance consumed path-major (`household.members` order, one `_draw_death_age()` call per member per path), per research.md §5 and contracts/simulation-api.md (depends on T002)
- [X] T004 [P] Export `generate_death_age_draws` from `src/retirement_planner/simulation/__init__.py`, alongside the existing `SURVIVAL_TABLE`/`generate_return_paths` exports (depends on T003)

**Checkpoint**: `mortality.py` exists, importable, ready for `monte_carlo.py` to consume.

---

## Phase 3: User Story 1 - A Monte Carlo run's own success rate reflects survivor risk (Priority: P1) 🎯 MVP

**Goal**: Given survival curves for one or more household members and this capability enabled, each
Monte Carlo path draws its own death age per covered member and is funded/scored as if that death
actually happened — so `success_rate`/`percentile_bands` themselves vary with survivor risk, not
just the separate post-hoc `survival_adjusted_success_rate` metric.

**Independent Test**: Configure a married household with both members' survival curves supplied,
enable this capability, run a Monte Carlo simulation, and confirm draws vary path-to-path and a
path's own outcome reflects its own drawn death year exactly as `018` already produces for a
deterministic projection given that death year (quickstart.md §1).

### Implementation for User Story 1

- [X] T005 [US1] Add a private helper `_household_for_path(household: Household, death_year_draw: dict[str, int | None] | None) -> Household` to `src/retirement_planner/simulation/monte_carlo.py`: returns `household` unchanged (same object) when `death_year_draw is None`; otherwise returns `dataclasses.replace(household, members=[dataclasses.replace(m, predicted_death_age=death_year_draw[m.person_name]) for m in household.members])`, per research.md §6 and data-model.md
- [X] T006 [US1] Add `death_year_draws: list[dict[str, int | None]] | None = None` to `run_simulation()`'s signature in `monte_carlo.py`, with eager validation before any path is scored: `ValueError` if given while `survival_curves is None`; `ValueError` if `len(death_year_draws) != len(return_paths)` — per contracts/simulation-api.md and research.md §3 (depends on T005)
- [X] T007 [US1] Change `_run_one_path()`'s call-args tuple and `_run_one_path_shared()`'s per-task parameter from carrying `return_path: ReturnPath` alone to carrying `(return_path, death_year_draw)` pairs; both now call `_household_for_path(household, death_year_draw)` and pass its result as `run_plan_projection()`'s `household` argument instead of the raw `household` (research.md §7) (depends on T005)
- [X] T008 [US1] Update `run_simulation()`'s serial-dispatch `call_args` list comprehension and parallel-dispatch `executor.map()` call to zip `return_paths` with `death_year_draws if death_year_draws is not None else [None] * len(return_paths)`, matching T007's new per-call/per-task shape in both dispatch modes (depends on T006, T007)
- [X] T009 [US1] Update `run_simulation()`'s and `monte_carlo.py`'s module docstrings to describe the new opt-in capability and its relationship to `survival_adjusted_success_rate`, per contracts/simulation-api.md (depends on T006, T007, T008)

### Tests for User Story 1

- [X] T010 [P] [US1] Unit tests in new `tests/unit/simulation/test_mortality.py`: `_draw_death_age()`'s three boundary rules (`current_age` at/below 50 → treated as certain-alive; above 110 → uses the oldest documented probability; in-range → direct lookup, no interpolation); `generate_death_age_draws()` raises `ValueError` for `path_count <= 0` and `KeyError` for a household member missing from `survival_curves` (depends on T003)
- [X] T011 [P] [US1] Distribution tests in `test_mortality.py`: across a large sample (e.g. 10,000 draws) for a fixed `current_age`, 100% of non-`None` draws are `>= current_age` (SC-002); a `None` draw occurs only when no documented age `>= current_age` satisfies the threshold (i.e. is consistent with the curve's own oldest documented probability)
- [X] T012 [P] [US1] Reproducibility unit test in `test_mortality.py`: `generate_death_age_draws()` called twice with identical `household`/`survival_curves`/`path_count`/`seed` returns byte-for-byte identical results (SC-003, first half) (depends on T003)
- [X] T013 [US1] Unit tests in `tests/unit/simulation/test_monte_carlo.py`: `death_year_draws=None` (the default) produces `run_simulation()` output byte-for-byte identical to the parameter being omitted entirely, for a fixture that also configures `survival_curves` (FR-007, SC-005); a supplied `death_year_draws` causes a specific path's `path_results[i]`'s post-death-year `filing_status`/Social-Security/spending values to match exactly what a direct `run_plan_projection()` call with that same drawn `predicted_death_age` produces (Acceptance Scenario 2); a path whose draw is `None` for a member behaves identically to that member having no `predicted_death_age` at all for that path (Acceptance Scenario 3) (depends on T008)
- [X] T014 [P] [US1] Validation-error unit tests in `tests/unit/simulation/test_survival.py`: `run_simulation()` raises `ValueError` when `death_year_draws` is given with `survival_curves=None`; raises `ValueError` when `len(death_year_draws) != len(return_paths)` (contracts/simulation-api.md) (depends on T006)

**Checkpoint**: User Story 1 fully functional and independently testable — SC-001, SC-002, SC-003 (generation half), SC-005 satisfied.

---

## Phase 4: User Story 2 - Draws stay reproducible and paired across comparisons (Priority: P2)

**Goal**: Confirm the same guarantees `return_paths` already provides — reproducibility across
repeated runs and dispatch modes, and identical reuse across every comparison candidate — now also
hold for `death_year_draws`.

**Independent Test**: Run the same scenario/path-count/seed under both serial and forced-parallel
dispatch and confirm identical draws/results; run a paired-draw comparison and confirm every
candidate's path `i` reflects the identical drawn death year(s) (quickstart.md §2).

### Implementation for User Story 2

- [X] T015 [P] [US2] Add `death_year_draws: list[dict[str, int | None]] | None = None` to `compare_states()` in `src/retirement_planner/simulation/compare.py`, forwarded unchanged to its own `run_simulation()` call, in the same position as the existing `survival_curves` parameter (research.md §2)
- [X] T016 [P] [US2] Same passthrough addition to `compare_roth_conversion_strategies()` in `compare.py`
- [X] T017 [P] [US2] Same passthrough addition to `compare_withdrawal_sequencing_strategies()` in `compare.py`
- [X] T018 [P] [US2] Same passthrough addition to `compare_claiming_age_grid()` in `compare.py`

### Tests for User Story 2

- [X] T019 [US2] Serial-vs-parallel dispatch parity unit test in `tests/unit/simulation/test_monte_carlo.py`: the same `household`/`return_paths`/`death_year_draws`/every other input, run once under serial dispatch and once forced into parallel dispatch (mirroring this test file's own existing convention for forcing dispatch mode), produce identical `success_rate`, `percentile_bands`, and every path's own `path_results[i]` (SC-003, second half) (depends on T008)
- [X] T020 [P] [US2] Paired-draw unit test in `tests/unit/simulation/test_compare.py`: `compare_states()` (or another `compare_*()`) called with `death_year_draws` set across two or more candidates shows every candidate's `path_results[i]`'s `filing_status`/Social-Security sequence identical to every other candidate's `path_results[i]` (Acceptance Scenario 3, SC-004) (depends on T015)

**Checkpoint**: User Story 2 confirmed — SC-003, SC-004 fully satisfied.

---

## Phase 5: User Story 3 - The new capability and its simplifications are documented (Priority: P3)

**Goal**: `docs/BRD.md` describes this opt-in capability, its current-age-conditioning design choice,
and its disclosed simplifications.

**Independent Test**: Read `docs/BRD.md`'s simulation-engine section and confirm it describes the
new capability and its disclosed gaps (quickstart.md §3).

### Implementation for User Story 3

- [X] T021 [US3] Update `docs/BRD.md`'s simulation-engine / mortality section (the section `005`/`018` describe `survival_adjusted_success_rate`/the Monte Carlo per-path gap in) per FR-011: describe per-path probabilistic death draws as a new, opt-in, off-by-default Monte Carlo capability, distinct from and coexisting with `survival_adjusted_success_rate`; list its disclosed simplifications — current-age conditioning (and how/why it differs from the older unconditional check), the still-illustrative/unverified `SURVIVAL_TABLE`, independence from returns and from the other member's own draw (no joint/correlated sampling), reuse of `018`'s earlier-death-wins rule, and no BFF/UI wiring yet (depends on T009, T015)

**Checkpoint**: All three user stories independently functional — SC-007 satisfied.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Confirm the constitution's Performance Budget gate empirically (not assumed) and run
the full regression suite.

- [X] T022 Add a reference-scale benchmark case to `tests/integration/test_simulation_performance.py`: the existing reference-scale household/market/strategy fixture, 3,000-5,000 paths, with `survival_curves` and `death_year_draws` (generated via `generate_death_age_draws()`) both supplied, asserting completion well under one minute — mirroring this file's existing benchmark structure exactly (FR-012, SC-006) (depends on T008)
- [X] T023 Run the full `pytest tests/` suite and confirm 100% pass, including every pre-existing test unmodified by this feature (final regression confirmation, SC-005) (depends on T001-T022)
- [X] T024 Update `README.md`'s core-library test count if the total changed (living-documentation convention, CLAUDE.md) (depends on T023)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user story phases.
- **User Story 1 (Phase 3)**: Depends on Foundational only. The MVP — delivers the entire
  observable behavior change (a Monte Carlo run's own success rate reflecting survivor risk).
- **User Story 2 (Phase 4)**: Depends on User Story 1's implementation (T005-T008) being complete —
  it threads the same mechanism through `compare.py` and verifies the reuse/reproducibility
  guarantees that mechanism was built to satisfy from the start.
- **User Story 3 (Phase 5)**: Depends on User Story 1 (T009) and User Story 2 (T015) — it documents
  both stories' completed behavior.
- **Polish (Phase 6)**: Depends on User Story 1's T008 (the full per-path wiring) — pointless to
  benchmark before it exists.

### Within Each Phase

- Foundational: T002 → T003 (same file, sequential); T004 depends on T003.
- User Story 1: T005 → T006 → T007 → T008 → T009 (each builds on the previous change to the same
  two files); then T010/T011/T012/T014 in parallel with each other once T003/T006 exist; T013
  depends on T008.
- User Story 2: T015/T016/T017/T018 in parallel (four independent functions in one file, each a
  one-line passthrough addition); T019 depends on T008 directly (not on Phase 4's own T015-T018);
  T020 depends on T015.
- User Story 3: T021 only.
- Polish: T022 → T023 → T024, in sequence.

### Parallel Opportunities

- User Story 1: T010, T011, T012, and T014 in parallel once their respective dependencies land (all
  test-only, three against `test_mortality.py`, one against `test_survival.py`).
- User Story 2: T015-T018 in parallel — four independent one-line additions to the same file's four
  distinct functions; sequence only if a single implementer prefers one file edit at a time.
- **File-contention note**: T005, T006, T007, and T008 all edit `monte_carlo.py`'s tightly-coupled
  path-dispatch machinery — sequence these rather than attempting them concurrently, mirroring
  `018`'s own note about its single-story tightly-coupled sequence.

---

## Parallel Example: User Story 1 (tests)

```bash
Task: "Boundary-rule and error-case tests in tests/unit/simulation/test_mortality.py (T010)"
Task: "Distribution/SC-002 sanity test in tests/unit/simulation/test_mortality.py (T011)"
Task: "Reproducibility test in tests/unit/simulation/test_mortality.py (T012)"
Task: "Validation-error tests in tests/unit/simulation/test_survival.py (T014)"
```

## Parallel Example: User Story 2 (implementation)

```bash
Task: "death_year_draws passthrough in compare_states() (T015)"
Task: "death_year_draws passthrough in compare_roth_conversion_strategies() (T016)"
Task: "death_year_draws passthrough in compare_withdrawal_sequencing_strategies() (T017)"
Task: "death_year_draws passthrough in compare_claiming_age_grid() (T018)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational) — `generate_death_age_draws()` exists and is
   independently correct.
2. Complete Phase 3 (User Story 1) — a Monte Carlo run's own `success_rate`/`percentile_bands`
   already reflect survivor risk when this capability is enabled.
3. **STOP and VALIDATE**: run `pytest tests/unit/simulation/test_mortality.py
   tests/unit/simulation/test_monte_carlo.py tests/unit/simulation/test_survival.py` and confirm
   green. This alone delivers the entire observable capability rp-vgv exists for (SC-001, SC-002,
   SC-005).

### Incremental Delivery

1. Setup + Foundational → the draw-generation primitive is ready and independently tested.
2. User Story 1 → the per-path override ships in `run_simulation()`; Monte Carlo output now varies
   with survivor risk when this capability is opted into.
3. User Story 2 → the same mechanism is threaded through every `compare_*()` function and its
   reproducibility/paired-draw guarantees are confirmed at that layer too.
4. User Story 3 → `docs/BRD.md` catches up with what's now true.
5. Polish → the reference-scale performance budget is confirmed empirically and the full suite is
   green.

Each phase leaves the repository in a fully working, fully tested state — a stop after any phase is
a valid, shippable increment.
