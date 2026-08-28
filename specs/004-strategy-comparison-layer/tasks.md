---

description: "Task list for Strategy Comparison Layer"
---

# Tasks: Strategy Comparison Layer

**Input**: Design documents from `/specs/004-strategy-comparison-layer/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/comparison-api.md](./contracts/comparison-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Project Structure and the constitution's Development Workflow gate ("unit test coverage for numeric primitives") both specify test files as deliverables of this feature, matching the precedent set by `001`, `002`, and `003`.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3/P4) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths are exact and relative to the repository root

## Path Conventions

Single Python library project, `src/` layout, per [plan.md](./plan.md) Project Structure:
- Library code: `src/retirement_planner/comparison/`, plus one registry addition in `src/retirement_planner/mechanics/withdrawal_sequencing.py`
- Tests: `tests/unit/comparison/`, `tests/unit/mechanics/`, `tests/integration/`

No new runtime dependencies are needed (plan.md Technical Context) — `pyproject.toml` is unchanged. This feature imports from the existing `retirement_planner.scenario`, `retirement_planner.tax`, and `retirement_planner.mechanics` packages; only `mechanics/withdrawal_sequencing.py` gains one registry entry (research.md §8) — no other file in `001`–`003` changes.

**Important — this feature's stories are NOT mutually independent**, unlike `001`–`003`: spec.md's own "Why this priority" reasoning states that User Stories 2, 3, and 4 each reuse User Story 1's full-horizon projection mechanism, varying only one dimension. Concretely, `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, and `compare_claiming_age_grid()` are all thin loops over `run_plan_projection()` (contracts/comparison-api.md), so each of US2/US3/US4 requires US1's `run_plan_projection()` to exist first. US2, US3, and US4 have no dependency on each other, so once US1 is done they can proceed in any order or in parallel.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create the comparison subpackage directory skeleton: `src/retirement_planner/comparison/__init__.py`, `tests/unit/comparison/__init__.py` (mirrors `003`'s `mechanics/` layout; `tests/integration/` already exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data shapes and the return-blending formula every user story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Define all shared comparison data types in `src/retirement_planner/comparison/models.py`: `DeterministicReturnAssumption`, `StrategyConfiguration`, `PlanYearProjection`, `PlanOutcome`, `PlanProjection`, `ComparisonDimension`, `ComparisonResult` — importing `AccountBalances`, `WithdrawalPlan`, `PlanYearMechanicsResult` from `retirement_planner.mechanics` and `FederalTaxResult`, `StateTaxResult`, `FigureUsage` from `retirement_planner.tax` rather than redefining them, exactly matching the shapes in [data-model.md](./data-model.md) and [contracts/comparison-api.md](./contracts/comparison-api.md)
- [X] T003 [P] Unit test `derive_deterministic_return()` against hand-calculated allocation-weighted blends of `equity_return_mean_real`/`bond_return_mean_real`, confirming `equity_return_std_real`, `bond_return_std_real`, and `correlation` are ignored (research.md §1) in `tests/unit/comparison/test_returns.py` (depends on T002)
- [X] T004 Implement `derive_deterministic_return()` in `src/retirement_planner/comparison/returns.py` (FR-003) (depends on T002, T003)
- [X] T005 Wire the public exports in `src/retirement_planner/comparison/__init__.py` — re-export every type from T002 and `derive_deterministic_return` from T004 (function exports from `projection.py` and `compare.py` are added as their user stories land) (depends on T002, T004)

**Checkpoint**: Foundation ready — User Story 1 implementation can now begin

---

## Phase 3: User Story 1 - Project a single plan across its full retirement horizon (Priority: P1) 🎯 MVP

**Goal**: Given a household, starting account balances, a spending need, a state, and one strategy configuration, run RMD → withdrawal sequencing → Roth conversion → federal/state tax → tax-funded withdrawal → investment growth for every plan year from the start of retirement through the planning horizon, carrying balances forward year to year.

**Independent Test**: Feed one complete scenario and one `StrategyConfiguration` into `run_plan_projection()` and confirm the result contains one correctly-linked entry per plan year, with the final `PlanOutcome` derived correctly from that history.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T014–T016

- [X] T006 [P] [US1] Unit test `run_plan_projection()` translates each household member's age in a given plan year from `current_age` and `reference_tax_year` (research.md §2) in `tests/unit/comparison/test_projection.py`
- [X] T007 [US1] Unit test `run_plan_projection()` attributes RMD determination to the older household member's translated age and always passes `spouse_is_sole_beneficiary=False` to `compute_rmd()` (research.md §3–4) in `tests/unit/comparison/test_projection.py`
- [X] T008 [US1] Unit test `run_plan_projection()` computes each plan year's household gross Social Security benefit from every member's `ss_annual_benefit`, included only once that year's translated age reaches `strategy.claiming_ages[person_name]` (data-model.md § Relationships) in `tests/unit/comparison/test_projection.py`
- [X] T009 [US1] Unit test `run_plan_projection()` funds a plan year's `federal_tax_owed + state_tax_owed` via a second `compute_withdrawal_plan()` call against the post-mechanics balances, using the same `withdrawal_strategy`, and adds its `shortfall` into the year's total (research.md §5) in `tests/unit/comparison/test_projection.py`
- [X] T010 [US1] Unit test `run_plan_projection()` applies `return_assumption.annual_real_return` identically to all three account types between plan years, so year N+1's `starting_balances` equals year N's post-tax-funding `ending_balances` grown by that rate (research.md §6, Acceptance Scenario US1.2) in `tests/unit/comparison/test_projection.py`
- [X] T011 [US1] Unit test `run_plan_projection()` records a plan year's shortfall and continues computing every subsequent year with the affected account type(s) floored at `0`, never negative and never raising (Acceptance Scenario US1.3, research.md §7) in `tests/unit/comparison/test_projection.py`
- [X] T012 [US1] Unit test `run_plan_projection()` called twice with identical scenario, strategy, and return assumption produces identical `PlanProjection` results (Acceptance Scenario US1.4, FR-012) in `tests/unit/comparison/test_projection.py`
- [X] T013 [US1] Integration test: run quickstart.md §1 (full-horizon projection, balance carry-forward, reproducibility) in `tests/integration/test_comparison_lifecycle.py`

### Implementation for User Story 1

- [X] T014 [US1] Implement the per-plan-year private helpers in `src/retirement_planner/comparison/projection.py` — age translation (research.md §2), deemed-RMD-owner selection (research.md §4), and household gross Social Security benefit for a year (research.md, data-model.md § Relationships) (depends on T005)
- [X] T015 [US1] Implement `run_plan_projection()` in `src/retirement_planner/comparison/projection.py` — orchestrates, for each plan year: `compute_rmd()` → `compute_plan_year_mechanics()` → `compute_federal_tax()`/`compute_state_tax()` → the tax-funding `compute_withdrawal_plan()` call → growth (research.md §5–§7); assembles the `years` list and derives `PlanOutcome` (FR-001, FR-002, FR-004) (depends on T014)
- [X] T016 [US1] Add `run_plan_projection` to `src/retirement_planner/comparison/__init__.py` exports (depends on T015)

**Checkpoint**: User Story 1 is independently functional — a full-horizon projection can be run and inspected for one strategy configuration. No comparison across configurations (US2/US3/US4) yet.

---

## Phase 4: User Story 2 - Compare Roth conversion strategies against each other (Priority: P2)

**Goal**: Run the identical full-horizon projection under each of a list of Roth conversion strategies (fill-to-10%-bracket, fill-to-22%-bracket, fixed dollar amount, no conversion), holding every other input — including the market return assumption — fixed, and return one outcome per strategy in a single structured comparison.

**Independent Test**: Feed one scenario and the four named conversion strategies into `compare_roth_conversion_strategies()` and confirm one outcome per strategy, all sharing the identical `return_assumption`, differing only where the strategies' rules actually diverge.

### Tests for User Story 2 ⚠️

- [X] T017 [P] [US2] Unit test `compare_roth_conversion_strategies()` returns one `PlanProjection` per candidate, every one carrying the identical `return_assumption` passed in (FR-005, FR-009, Acceptance Scenario US2.1) in `tests/unit/comparison/test_compare_roth_conversion.py`
- [X] T018 [US2] Unit test `compare_roth_conversion_strategies()` produces a different `cumulative_tax_paid` and `ending_balance` between `"no_conversion"` and a `"fill_to_bracket"` candidate (Acceptance Scenario US2.2) in `tests/unit/comparison/test_compare_roth_conversion.py`
- [X] T019 [US2] Unit test `compare_roth_conversion_strategies()` returns identical outcomes for two candidates whose configured amounts happen to produce identical annual conversions for a given scenario (Acceptance Scenario US2.3) in `tests/unit/comparison/test_compare_roth_conversion.py`
- [X] T020 [US2] Unit test `compare_roth_conversion_strategies()` overwrites every candidate's `withdrawal_strategy` and `claiming_ages` with this call's shared values before running, so only the conversion dimension varies (contracts/comparison-api.md) in `tests/unit/comparison/test_compare_roth_conversion.py`
- [X] T021 [US2] Integration test: run quickstart.md §2 (four named Roth conversion strategies compared) in `tests/integration/test_comparison_lifecycle.py`

### Implementation for User Story 2

- [X] T022 [US2] Implement `compare_roth_conversion_strategies()` in `src/retirement_planner/comparison/compare.py` — loops `run_plan_projection()` once per candidate, forcing the call's shared `withdrawal_strategy`/`claiming_ages`/`return_assumption` onto every candidate (FR-005, FR-009) (depends on T015)
- [X] T023 [US2] Add `compare_roth_conversion_strategies` to `src/retirement_planner/comparison/__init__.py` exports (depends on T022)

**Checkpoint**: User Stories 1 and 2 are both functional — Roth conversion strategies can be compared under identical market conditions. No withdrawal-order (US3) or claiming-age (US4) comparison yet.

---

## Phase 5: User Story 3 - Compare withdrawal sequencing orders against each other (Priority: P3)

**Goal**: Run the identical full-horizon projection under two or more withdrawal sequencing orders, holding the Roth conversion strategy, claiming ages, and market return assumption fixed, and return one outcome per order.

**Independent Test**: Feed one scenario and two withdrawal orders (`003`'s shipped default plus this feature's added second order) into `compare_withdrawal_sequencing_strategies()` and confirm one outcome per order, differing only from draw-order effects.

### Tests for User Story 3 ⚠️

- [X] T024 [P] [US3] Unit test `compute_withdrawal_plan(strategy="rmd_traditional_taxable_roth")` draws traditional before taxable, with RMD still the unconditional first leg (FR-007, research.md §8) in `tests/unit/mechanics/test_withdrawal_sequencing.py`
- [X] T025 [P] [US3] Unit test `compare_withdrawal_sequencing_strategies()` returns one `PlanProjection` per candidate order, every one sharing the identical `conversion_strategy`, `claiming_ages`, and `return_assumption` passed in (FR-006, FR-009, Acceptance Scenario US3.1) in `tests/unit/comparison/test_compare_withdrawal_sequencing.py`
- [X] T026 [US3] Unit test `compare_withdrawal_sequencing_strategies()` produces a different `cumulative_tax_paid` or `ending_balance` between `"rmd_taxable_traditional_roth"` and `"rmd_traditional_taxable_roth"` candidates (Acceptance Scenario US3.2) in `tests/unit/comparison/test_compare_withdrawal_sequencing.py`
- [X] T027 [US3] Unit test `compare_withdrawal_sequencing_strategies()` converges both orders' later-year outcomes once one account type is exhausted under both (Acceptance Scenario US3.3) in `tests/unit/comparison/test_compare_withdrawal_sequencing.py`
- [X] T028 [US3] Integration test: run quickstart.md §3 (two withdrawal orders compared) in `tests/integration/test_comparison_lifecycle.py`

### Implementation for User Story 3

- [X] T029 [US3] Add `"rmd_traditional_taxable_roth" -> ("traditional", "taxable", "roth")` to `WITHDRAWAL_STRATEGIES` in `src/retirement_planner/mechanics/withdrawal_sequencing.py` — the only change to `003`'s package this feature makes (research.md §8) (depends on T024)
- [X] T030 [US3] Implement `compare_withdrawal_sequencing_strategies()` in `src/retirement_planner/comparison/compare.py` — loops `run_plan_projection()` once per candidate, forcing the call's shared `conversion_strategy`/`conversion_bracket_ceiling_or_amount`/`conversion_window`/`claiming_ages`/`return_assumption` onto every candidate (FR-006, FR-009) (depends on T015, T029)
- [X] T031 [US3] Add `compare_withdrawal_sequencing_strategies` to `src/retirement_planner/comparison/__init__.py` exports (depends on T030)

**Checkpoint**: User Stories 1–3 are all functional — Roth conversion strategies and withdrawal orders can each be compared independently. No claiming-age comparison (US4) yet.

---

## Phase 6: User Story 4 - Compare Social Security claiming-age combinations against each other (Priority: P4)

**Goal**: Run the identical full-horizon projection across a caller-supplied grid of claiming-age pairs, holding the Roth conversion strategy, withdrawal order, and market return assumption fixed, and return one outcome per pair.

**Independent Test**: Feed one scenario and the full 62–70 claiming-age grid into `compare_claiming_age_grid()` and confirm one outcome per pair, with the pair matching the scenario's originally configured ages reproducing User Story 1's standalone result exactly.

### Tests for User Story 4 ⚠️

- [X] T032 [P] [US4] Unit test `compare_claiming_age_grid()` returns one `PlanProjection` per grid entry, every one sharing the identical `withdrawal_strategy`, `conversion_strategy`, and `return_assumption` passed in (FR-008, FR-009, Acceptance Scenario US4.1) in `tests/unit/comparison/test_compare_claiming_age_grid.py`
- [X] T033 [US4] Unit test `compare_claiming_age_grid()` produces different Social Security income timing and ending balance between an earlier-claim and a later-claim pair (Acceptance Scenario US4.2) in `tests/unit/comparison/test_compare_claiming_age_grid.py`
- [X] T034 [US4] Unit test `compare_claiming_age_grid()`'s outcome for the grid entry matching the scenario's originally configured claiming ages equals `run_plan_projection()`'s standalone result for the same scenario exactly (Acceptance Scenario US4.3) in `tests/unit/comparison/test_compare_claiming_age_grid.py`
- [X] T035 [US4] Unit test `compare_claiming_age_grid()` raises `ValueError` when any grid entry names a claiming age outside 62–70 inclusive (FR-010, Edge Cases) in `tests/unit/comparison/test_compare_claiming_age_grid.py`
- [X] T036 [US4] Integration test: run quickstart.md §4 (full 62–70 claiming-age grid) in `tests/integration/test_comparison_lifecycle.py`

### Implementation for User Story 4

- [X] T037 [US4] Implement `compare_claiming_age_grid()` in `src/retirement_planner/comparison/compare.py` — validates every grid entry's ages against the 62–70 bounds (FR-010) before running, then loops `run_plan_projection()` once per entry, forcing the call's shared `withdrawal_strategy`/`conversion_strategy`/`conversion_bracket_ceiling_or_amount`/`conversion_window`/`return_assumption` onto every entry (FR-008, FR-009) (depends on T015)
- [X] T038 [US4] Add `compare_claiming_age_grid` to `src/retirement_planner/comparison/__init__.py` exports (depends on T037)

**Checkpoint**: All four user stories are independently functional — full-horizon projection, Roth conversion comparison, withdrawal-order comparison, and claiming-age comparison each work correctly, per [quickstart.md](./quickstart.md) steps 1–4.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify the feature's cross-cutting requirements (single-candidate comparisons, performance) and tie the quickstart walkthrough together as one acceptance run

- [X] T039 [P] Unit test `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, and `compare_claiming_age_grid()` each accept a single-entry candidate/grid list and still return a valid one-entry `ComparisonResult` (FR-011, Edge Cases) in `tests/unit/comparison/test_compare_roth_conversion.py`, `tests/unit/comparison/test_compare_withdrawal_sequencing.py`, and `tests/unit/comparison/test_compare_claiming_age_grid.py` respectively (depends on T022, T030, T037)
- [X] T040 Run the complete [quickstart.md](./quickstart.md) walkthrough (all 4 sections) as one end-to-end assertion sequence in `tests/integration/test_comparison_lifecycle.py` (depends on T013, T021, T028, T036)
- [X] T041 [P] Add docstrings to every public function/dataclass in `src/retirement_planner/comparison/{models,returns,projection,compare}.py` referencing the corresponding section of [contracts/comparison-api.md](./contracts/comparison-api.md) (depends on T004, T015, T022, T030, T037)
- [X] T042 [P] Add a lightweight timing check confirming the full 9×9 claiming-age grid comparison (35-year horizon) completes within a few seconds (plan.md Performance Goals, Constitution Principle VI) in `tests/integration/test_comparison_performance.py` (depends on T037)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational **and** User Story 1's `run_plan_projection()` (T015) — `compare_roth_conversion_strategies()` calls it directly
- **User Story 3 (Phase 5)**: Depends on Foundational, User Story 1's `run_plan_projection()` (T015), and the existing `retirement_planner.mechanics` package (`003`) for its own registry addition (T029) — independent of US2
- **User Story 4 (Phase 6)**: Depends on Foundational and User Story 1's `run_plan_projection()` (T015) only — independent of US2 and US3
- **Polish (Phase 7)**: `T039` depends on US2/US3/US4's compare functions (`T022`, `T030`, `T037`); `T040`–`T042` depend on all four user stories

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — the MVP slice, and the only story every other one builds on
- **User Story 2 (P2)**: Depends on US1's `run_plan_projection()` existing; no dependency on US3 or US4 — can be built in parallel with either once US1 is done
- **User Story 3 (P3)**: Depends on US1's `run_plan_projection()` existing; no dependency on US2 or US4 — can be built in parallel with either once US1 is done
- **User Story 4 (P4)**: Depends on US1's `run_plan_projection()` existing; no dependency on US2 or US3 — can be built in parallel with either once US1 is done
- Unlike `001`–`003`, this feature's later stories are genuinely sequential relative to its first story (see the note at the top of this document) — but US2, US3, and US4 are fully parallel relative to *each other*

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task
- Foundational models (T002) and the return-blending formula (T004) before any story-specific code
- Within US1: the private per-year helpers (T014) before `run_plan_projection()` (T015), which consumes them
- Within US3: the new registry entry (T029) before `compare_withdrawal_sequencing_strategies()` (T030), which needs it to have a second order to run

### Parallel Opportunities

- T002 and T003 can start together once T001 is done (T003 needs T002's types but not T004's implementation) — write the test against the not-yet-implemented function, confirm it fails, then implement T004
- T006 (US1's first test) can start alongside T024 (US3's mechanics registry test, a different, pre-existing file) as soon as Foundational is done — T024 has no dependency on any comparison-package code
- **User Story 2, User Story 3, and User Story 4 can all be built fully in parallel** by different contributors once User Story 1 (`T015`) is done, since none depends on another's code — only US1 is a hard prerequisite for all three
- T041 (docstrings) and T042 (performance check) can run in parallel — separate files

---

## Parallel Example: User Stories 2–4 (post-US1)

```bash
# Launch the first test for each remaining user story together, in three different files:
Task: "Unit test compare_roth_conversion_strategies() shares return_assumption in tests/unit/comparison/test_compare_roth_conversion.py"
Task: "Unit test compute_withdrawal_plan() new registry order in tests/unit/mechanics/test_withdrawal_sequencing.py"
Task: "Unit test compare_claiming_age_grid() shares return_assumption in tests/unit/comparison/test_compare_claiming_age_grid.py"

# Launch each story's implementation task together (all import run_plan_projection, none imports another's compare function):
Task: "Implement compare_roth_conversion_strategies() in src/retirement_planner/comparison/compare.py"
Task: "Implement compare_withdrawal_sequencing_strategies() in src/retirement_planner/comparison/compare.py"
Task: "Implement compare_claiming_age_grid() in src/retirement_planner/comparison/compare.py"
```

(Note: all three compare functions land in the same `compare.py` file per plan.md's Project Structure — genuinely parallel authorship of that one file will need coordination or sequential merging even though the *logic* has no cross-dependency.)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest tests/unit/comparison/test_projection.py tests/integration/test_comparison_lifecycle.py` and confirm SC-001 holds
5. This alone proves the full-horizon projection engine — every comparison this feature offers is this same engine run more than once

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add User Story 1 → correct full-horizon projection → validate independently (SC-001) → this is the MVP
3. Add User Story 2 → Roth conversion strategy comparison → validate independently (SC-002, SC-005)
4. Add User Story 3 → withdrawal sequencing comparison → validate independently (SC-003, SC-005)
5. Add User Story 4 → claiming-age grid comparison → validate independently (SC-004, SC-005)
6. Polish → single-candidate edge case, full quickstart.md walkthrough, docstrings, performance check (SC-006)

### Suggested Team Split

User Story 1 must land first and cannot be parallelized across contributors (it is one orchestrator function). Once `run_plan_projection()` (T015) is merged, User Story 2, User Story 3, and User Story 4 can be built fully in parallel by three different contributors — each only calls `run_plan_projection()` and touches no other story's code, though all three land in the shared `compare.py` file (see the Parallel Example note above) and should coordinate on merge order or split that file into per-story modules if true concurrent authorship is needed.
