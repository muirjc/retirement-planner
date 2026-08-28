---

description: "Task list for Retirement Account Mechanics"
---

# Tasks: Retirement Account Mechanics

**Input**: Design documents from `/specs/003-retirement-account-mechanics/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/mechanics-api.md](./contracts/mechanics-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Project Structure and the constitution's Development Workflow gate ("unit test coverage for numeric primitives") both specify test files as deliverables of this feature, matching the precedent set by `001-scenario-config-management` and `002-tax-calculation-engine`.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and relative to the repository root

## Path Conventions

Single Python library project, `src/` layout, per [plan.md](./plan.md) Project Structure:
- Library code: `src/retirement_planner/mechanics/`
- Tests: `tests/unit/mechanics/`, `tests/integration/`

No new runtime dependencies are needed (plan.md Technical Context) — `pyproject.toml` is unchanged. This feature imports from the existing `retirement_planner.tax` package (`compute_taxable_social_security`, `SourcedFigure`, `FigureUsage`); no changes to `tax/` or `scenario/` are required.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create the mechanics subpackage directory skeleton: `src/retirement_planner/mechanics/__init__.py`, `tests/unit/mechanics/__init__.py` (mirrors `002`'s `tax/` layout; `tests/integration/` already exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data shapes every user story's code and tests are built on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Define all shared mechanics data types in `src/retirement_planner/mechanics/models.py`: `AccountType`, `AccountBalances`, `RmdResult`, `WithdrawalLineItem`, `WithdrawalPlan`, `ConversionResult`, `PlanYearMechanicsResult` — importing `FigureUsage` from `retirement_planner.tax.models` rather than redefining it, exactly matching the shapes in [data-model.md](./data-model.md) and [contracts/mechanics-api.md](./contracts/mechanics-api.md)
- [X] T003 Wire the public exports in `src/retirement_planner/mechanics/__init__.py` — re-export every type from T002 (function exports from `rmd.py`, `withdrawal_sequencing.py`, `roth_conversion.py`, and `plan_year.py` are added as their user stories land) (depends on T002)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Compute the legally required minimum distribution for a plan year (Priority: P1) 🎯 MVP

**Goal**: Given a household member's age, traditional account balance, and (where applicable) spouse age/sole-beneficiary status for a plan year, compute RMD using the IRS Uniform Lifetime Table, or the Joint Life and Last Survivor Table when the spouse is the sole beneficiary and more than 10 years younger.

**Independent Test**: Feed a range of reference ages and spouse-age pairs into `compute_rmd()` and confirm the divisor/amount match IRS Pub. 590-B reference values for both tables.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T007–T008

- [X] T004 [P] [US1] Unit test `compute_rmd()` against Uniform Lifetime Table reference ages, and returns `required_amount=0`/`table_used=None` below the RMD-required starting age or with a zero balance (SC-001, Acceptance Scenarios US1.1, US1.4, US1.5) in `tests/unit/mechanics/test_rmd.py`
- [X] T005 [US1] Unit test `compute_rmd()` selects the Joint Life and Last Survivor Table only when `spouse_is_sole_beneficiary=True` and `member_age - spouse_age > 10`, and falls back to the Uniform Lifetime Table otherwise (SC-002, Acceptance Scenarios US1.2–1.3) in `tests/unit/mechanics/test_rmd.py`
- [X] T006 [US1] Unit test `compute_rmd()` raises `UnsupportedTaxYearError` when the RMD-required starting age figure or the divisor table actually needed has no schedule entry for the requested tax year in `tests/unit/mechanics/test_rmd.py`

### Implementation for User Story 1

- [X] T007 [US1] Implement `RMD_START_AGE`, `UNIFORM_LIFETIME_TABLE`, and `JOINT_LIFE_TABLE` as `SourcedFigure` constants (tax year 2026, illustrative placeholder values per IRS Pub. 590-B, `verified=False`) in `src/retirement_planner/mechanics/rmd.py` (depends on T002)
- [X] T008 [US1] Implement `compute_rmd()` in `src/retirement_planner/mechanics/rmd.py` — table-selection logic (FR-001–FR-003) and `figures_used` assembly reusing `002`'s `SourcedFigure`/`FigureUsage` convention (FR-019) (depends on T007)
- [X] T009 [US1] Add `compute_rmd`, `RMD_START_AGE`, `UNIFORM_LIFETIME_TABLE`, `JOINT_LIFE_TABLE` to `src/retirement_planner/mechanics/__init__.py` exports (depends on T008)
- [X] T010 [US1] Integration test: run quickstart.md step 1 (Uniform Lifetime vs. Joint Life table selection, below-start-age and zero-balance always $0) in `tests/integration/test_mechanics_lifecycle.py` (depends on T008)

**Checkpoint**: User Story 1 is independently functional — RMD can be computed correctly for both tables. No withdrawal sequencing (US2) or Roth conversion (US3) yet.

---

## Phase 4: User Story 2 - Draw funds from accounts in a defined, swappable sequence to meet spending need (Priority: P2)

**Goal**: Given a plan year's spending need, an already-computed RMD amount, and starting account balances, compute a withdrawal plan that draws RMD first, then the remaining need in a configured, swappable non-RMD sequence (default: taxable, then traditional, then Roth), reporting any unmet shortfall explicitly.

**Independent Test**: Feed a spending need, RMD amount, and starting balances into `compute_withdrawal_plan()` and confirm draw order, per-account balance caps, shortfall reporting, and that swapping the configured sequence changes draw order with no code change.

### Tests for User Story 2 ⚠️

- [X] T011 [P] [US2] Unit test `compute_withdrawal_plan()` draws in the default order — RMD, then taxable, then traditional, then Roth (Acceptance Scenario US2.1) in `tests/unit/mechanics/test_withdrawal_sequencing.py`
- [X] T012 [US2] Unit test `compute_withdrawal_plan()` performs no further draws when the RMD amount alone meets the year's spending need (Acceptance Scenario US2.2) in `tests/unit/mechanics/test_withdrawal_sequencing.py`
- [X] T013 [US2] Unit test `compute_withdrawal_plan()` rolls the unmet remainder to the next account type in sequence once the current one is exhausted (Acceptance Scenario US2.3) in `tests/unit/mechanics/test_withdrawal_sequencing.py`
- [X] T014 [US2] Unit test `compute_withdrawal_plan()` reports an explicit `shortfall` and never drives an account balance negative when total available assets are insufficient (FR-007, Acceptance Scenario US2.4) in `tests/unit/mechanics/test_withdrawal_sequencing.py`
- [X] T015 [US2] Unit test `compute_withdrawal_plan()` honors a different `WITHDRAWAL_STRATEGIES` ordering passed via `strategy=`, with the draw order changing and zero mechanics code touched (SC-003, Acceptance Scenario US2.5) in `tests/unit/mechanics/test_withdrawal_sequencing.py`

### Implementation for User Story 2

- [X] T016 [US2] Implement the shared draw-down function and the `WITHDRAWAL_STRATEGIES` registry (`dict[str, tuple[AccountType, ...]]`, seeded with `"rmd_taxable_traditional_roth"` → `("taxable", "traditional", "roth")`) in `src/retirement_planner/mechanics/withdrawal_sequencing.py` (FR-004–FR-006) (depends on T002)
- [X] T017 [US2] Implement `compute_withdrawal_plan()` in `src/retirement_planner/mechanics/withdrawal_sequencing.py` — unconditional RMD leg first, then the configured non-RMD sequence via the shared draw-down function, with explicit shortfall reporting (FR-007) (depends on T016)
- [X] T018 [US2] Add `compute_withdrawal_plan` and `WITHDRAWAL_STRATEGIES` to `src/retirement_planner/mechanics/__init__.py` exports (depends on T017)
- [X] T019 [US2] Integration test: run quickstart.md step 2 (default sequence, RMD-only coverage, swapped sequence, shortfall reporting) in `tests/integration/test_mechanics_lifecycle.py` (depends on T017)

**Checkpoint**: User Stories 1 and 2 are both independently functional — RMD and withdrawal sequencing can each be computed correctly and independently. No Roth conversion (US3) yet.

---

## Phase 5: User Story 3 - Execute a Roth conversion within a defined window using a chosen strategy (Priority: P3)

**Goal**: Given a plan year inside the scenario's configured conversion window, compute the conversion amount under a chosen strategy — fill established ordinary income up to a bracket ceiling (using `002`'s Social Security taxability logic), or convert a fixed dollar amount — and cap it at the available traditional balance.

**Independent Test**: Feed a plan year, strategy configuration, established ordinary income, and account balances into `compute_roth_conversion()` and confirm the computed amount is correct, capped, and zero outside the window.

### Tests for User Story 3 ⚠️

- [X] T020 [P] [US3] Unit test `fill_to_bracket_ceiling()` fills up to the configured ceiling using taxable Social Security obtained from `retirement_planner.tax.social_security.compute_taxable_social_security()`, and returns `$0` (not negative) when established income already meets or exceeds the ceiling (FR-009, FR-015, Acceptance Scenarios US3.1, US3.5) in `tests/unit/mechanics/test_roth_conversion.py`
- [X] T021 [US3] Unit test `fixed_dollar_amount()` converts exactly the configured amount, or the remaining traditional balance if smaller (FR-010, Acceptance Scenario US3.3) in `tests/unit/mechanics/test_roth_conversion.py`
- [X] T022 [US3] Unit test `compute_roth_conversion()` returns a zeroed `ConversionResult` for a plan year outside `window`, and a non-zero result for the window's first and last years (FR-008, Acceptance Scenario US3.2) in `tests/unit/mechanics/test_roth_conversion.py`
- [X] T023 [US3] Unit test a computed conversion amount never exceeds the `traditional_balance` passed in, for both strategies (FR-011, Acceptance Scenario US3.4) in `tests/unit/mechanics/test_roth_conversion.py`
- [X] T024 [US3] Unit test the same year's income/balances produce different, independently correct amounts under `"fill_to_bracket"` vs. `"fixed_amount"` (SC-004, Acceptance Scenario US3.6) in `tests/unit/mechanics/test_roth_conversion.py`

### Implementation for User Story 3

- [X] T025 [US3] Implement `fill_to_bracket_ceiling()` in `src/retirement_planner/mechanics/roth_conversion.py` — calls `retirement_planner.tax.social_security.compute_taxable_social_security()` (FR-015) to determine taxable Social Security, then computes headroom to the configured ceiling, capped at `traditional_balance` (FR-009, FR-011) (depends on T002)
- [X] T026 [US3] Implement `fixed_dollar_amount()` in `src/retirement_planner/mechanics/roth_conversion.py` — converts `min(traditional_balance, fixed_amount)` with an identical call signature to `fill_to_bracket_ceiling()` (FR-010) (depends on T002)
- [X] T027 [US3] Implement the `CONVERSION_STRATEGIES` registry and `compute_roth_conversion()` dispatcher in `src/retirement_planner/mechanics/roth_conversion.py` — returns a zeroed result without calling any strategy when `plan_year` is outside `window` (FR-008) (depends on T025, T026)
- [X] T028 [US3] Add `compute_roth_conversion`, `fill_to_bracket_ceiling`, `fixed_dollar_amount`, `CONVERSION_STRATEGIES` to `src/retirement_planner/mechanics/__init__.py` exports (depends on T027)
- [X] T029 [US3] Integration test: run quickstart.md step 3 (fill-to-bracket inside the window, outside-window no-op, fixed-amount, strategy independence) in `tests/integration/test_mechanics_lifecycle.py` (depends on T027)

**Checkpoint**: All three user stories are independently functional — RMD, withdrawal sequencing, and Roth conversion each work correctly on their own, per [quickstart.md](./quickstart.md) steps 1–3.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Tie the three mechanics together for one plan year, and verify the feature as a whole against the spec's non-story requirements

- [X] T030 [US1][US2][US3] Unit test `compute_plan_year_mechanics()` computes the withdrawal plan before the conversion, so the conversion's available traditional balance already excludes the RMD amount — RMD dollars are structurally never also converted (FR-013, Edge Cases, research.md §6) in `tests/unit/mechanics/test_plan_year.py` (depends on T017, T027)
- [X] T031 Implement `compute_plan_year_mechanics()` orchestrator in `src/retirement_planner/mechanics/plan_year.py` — calls `compute_withdrawal_plan()` first, then `compute_roth_conversion()` using the withdrawal plan's post-RMD ending traditional balance; returns a zeroed `conversion` when no conversion plan is configured (depends on T017, T027)
- [X] T032 Add `compute_plan_year_mechanics` to `src/retirement_planner/mechanics/__init__.py` exports (depends on T031)
- [X] T033 Integration test: run quickstart.md step 4 (RMD dollars never also converted) in `tests/integration/test_mechanics_lifecycle.py` (depends on T031)
- [X] T034 Run the complete [quickstart.md](./quickstart.md) walkthrough (all 4 steps) as one end-to-end assertion sequence in `tests/integration/test_mechanics_lifecycle.py` (depends on T010, T019, T029, T033)
- [X] T035 Add docstrings to every public function/dataclass in `src/retirement_planner/mechanics/{models,rmd,withdrawal_sequencing,roth_conversion,plan_year}.py` referencing the corresponding section of [contracts/mechanics-api.md](./contracts/mechanics-api.md) (depends on T008, T017, T027, T031)
- [X] T036 [P] Add a lightweight timing check confirming a single plan year's RMD + withdrawal + conversion computation completes in well under 10ms (plan.md Performance Goals) in `tests/integration/test_mechanics_performance.py` (depends on T031)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational only — `compute_withdrawal_plan()` takes `rmd_amount` as a plain argument, so it does not call into US1's `compute_rmd()` code; the two are independently buildable
- **User Story 3 (Phase 5)**: Depends on Foundational and the already-existing `retirement_planner.tax` package (`002`) only — `compute_roth_conversion()` takes `traditional_balance` as a plain argument, so it does not call into US1's or US2's code either
- **Polish (Phase 6)**: `T030`–`T033` depend on both US2 (`T017`) and US3 (`T027`) being complete, since `compute_plan_year_mechanics()` composes both; `T034`–`T036` depend on all three user stories

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — the MVP slice
- **User Story 2 (P2)**: No dependency on US1 or US3 — can be built in parallel with either once Foundational is done
- **User Story 3 (P3)**: No dependency on US1 or US2 — can be built in parallel with either once Foundational is done; only depends on `002`'s already-shipped `compute_taxable_social_security()`
- Only the Polish-phase orchestrator (`compute_plan_year_mechanics()`) ties all three together — none of the three user stories requires another to be complete first

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task
- Foundational models before any story-specific code
- Within US1: figure constants (`T007`) before `compute_rmd()` (`T008`), which consumes them
- Within US2: the shared draw-down function/registry (`T016`) before the dispatcher (`T017`), which consumes it
- Within US3: both strategy functions (`T025`, `T026`) before the registry/dispatcher (`T027`), which consumes them

### Parallel Opportunities

- T004 (US1 test) can start alongside T011 (US2 test) and T020 (US3 test) — three different files, no shared dependency beyond Foundational
- T016 and the eventual T025/T026 (US2 and US3 implementation, different files) can proceed in parallel once Foundational is done
- **User Story 1, User Story 2, and User Story 3 can all be built fully in parallel** by different contributors once Foundational is done, since none depends on another's code — a stronger parallelism than `002` had (where US3 depended on US2's `sc.py`)
- T036 (performance check) can run in parallel with T035 (docstrings) — separate file

---

## Parallel Example: User Stories 1–3 (post-Foundational)

```bash
# Launch the first test for each user story together, in three different files:
Task: "Unit test compute_rmd() Uniform Lifetime Table in tests/unit/mechanics/test_rmd.py"
Task: "Unit test compute_withdrawal_plan() default order in tests/unit/mechanics/test_withdrawal_sequencing.py"
Task: "Unit test fill_to_bracket_ceiling() in tests/unit/mechanics/test_roth_conversion.py"

# Launch each story's first implementation task together:
Task: "Implement RMD SourcedFigure constants in src/retirement_planner/mechanics/rmd.py"
Task: "Implement withdrawal-sequencing draw-down function + registry in src/retirement_planner/mechanics/withdrawal_sequencing.py"
Task: "Implement fill_to_bracket_ceiling() in src/retirement_planner/mechanics/roth_conversion.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest tests/unit/mechanics/test_rmd.py tests/integration/test_mechanics_lifecycle.py` and confirm SC-001/SC-002 hold
5. This alone proves the RMD engine — the mandatory floor every other account mechanic in this feature builds on — is computed correctly, including the source document's flagged gap (the Joint Life Table branch)

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add User Story 1 → correct RMD (Uniform Lifetime + Joint Life) → validate independently (SC-001, SC-002) → this is the MVP
3. Add User Story 2 → swappable withdrawal sequencing → validate independently (SC-003, SC-005)
4. Add User Story 3 → swappable Roth conversion strategies → validate independently (SC-004)
5. Polish → `compute_plan_year_mechanics()` orchestrator (ties all three together, encodes the RMD-not-convertible rule) + full quickstart.md walkthrough + performance check

### Suggested Team Split

User Story 1, User Story 2, and User Story 3 can be built fully in parallel by three different contributors once Foundational is done — each depends only on `models.py` (already built) and, for US3, the already-shipped `retirement_planner.tax` package. Whoever finishes first can pick up the Polish-phase orchestrator, which is the only code in this feature that imports from more than one of the three mechanics modules.
