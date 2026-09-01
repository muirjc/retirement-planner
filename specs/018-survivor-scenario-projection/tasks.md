---

description: "Task list for 018-survivor-scenario-projection"
---

# Tasks: Survivor Scenario Projection Wiring

**Input**: Design documents from `/specs/018-survivor-scenario-projection/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The constitution's "Unit test coverage for numeric primitives" gate
(Development Workflow & Quality Gates) and this project's existing precedent (016, 017) require
new engine behavior to have unit tests against hand-calculated/reference values before it's used
in any comparative run.

**Organization**: Tasks are grouped by user story (spec.md) to enable independent implementation
and testing of each story. Unlike `017` (where US1 and US2 were two independent calculations),
here User Story 2 has **no new production code of its own** — research.md Decision 6 established
that `comparison/compare.py` needs zero changes, since every `compare_*()` function already
forwards `household` unchanged into each candidate's own `run_plan_projection()` call. US2's phase
is therefore verification-only, entirely dependent on US1's implementation already existing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project — `src/retirement_planner/`, `tests/` at repo root, plus the two additive packages
`services/bff/` and `apps/streamlit_ui/` (see plan.md Project Structure).

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before changing shared code.

- [X] T001 Run `pytest tests/` and confirm the existing suite is green before any change in this feature (baseline for regression comparison later)

**Checkpoint**: Baseline confirmed green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared data-model fields every later phase's implementation and tests reference —
`Household.survivor_spending_reduction_pct` (the new opt-in input) and
`PlanYearProjection.filing_status`/`.effective_spending_need` (the new per-year audit output both
US1's own tests and US2's comparison-propagation test assert against).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `survivor_spending_reduction_pct: float = 0.0` to `Household` in `src/retirement_planner/scenario/models.py`, with a docstring per data-model.md (fraction 0.0-1.0, default is a true no-op, consulted only for post-death plan years)
- [X] T003 [P] Add `filing_status: Literal["single", "married_filing_jointly"] | None = None` and `effective_spending_need: float = 0.0` to `PlanYearProjection` in `src/retirement_planner/comparison/models.py`, per data-model.md and contracts/comparison-api.md
- [X] T004 Parse the optional `survivor_spending_reduction_pct` field (float, default `0.0`) in `_build_household()` in `src/retirement_planner/scenario/loader.py`, mirroring the existing `hdhp_coverage` optional-field-defaults-to-a-no-op-value pattern (depends on T002)
- [X] T005 Add a plausibility **warning** rule to `_validate_household()` in `src/retirement_planner/scenario/validation.py`: a non-default `survivor_spending_reduction_pct` outside `[0.0, 1.0]` is flagged (not blocking — an intentional "spending goes up" scenario is a legitimate if unusual choice), per data-model.md (depends on T002)

**Checkpoint**: Shared fields exist and round-trip through YAML. User story implementation can now begin.

---

## Phase 3: User Story 1 - A projection shows the widow's tax penalty after a configured death (Priority: P1) 🎯 MVP

**Goal**: In an MFJ household with one member's `predicted_death_age` configured, a deterministic
projection switches to `single` filing status, survivor-benefit Social Security income, and
reduced spending need for every plan year after the death year — with every year before it, and
every household with no configured death, completely unaffected.

**Independent Test**: Configure an MFJ household with `predicted_death_age` set on one member, run
a deterministic projection, and confirm the pre/post-death split (quickstart.md §1); confirm a
household with no configured death is byte-for-byte unchanged (quickstart.md §2).

### Implementation for User Story 1

- [X] T006 [US1] Add a private helper `_household_death_tax_year(household, reference_tax_year) -> tuple[HouseholdMember, int] | None` to `src/retirement_planner/comparison/projection.py`: for an MFJ household (`filing_status == "married_filing_jointly"` and `len(members) == 2`) where at least one member has `predicted_death_age` set, returns `(dying_member, death_tax_year)` using the same age-translation arithmetic as `member_age_in_tax_year()`, inverted; when both members have it configured, returns the pair for the **earlier** tax year; `None` otherwise — per research.md Decision 1 and data-model.md § Derived (depends on T002)
- [X] T007 [US1] In `run_plan_projection()`, call `_household_death_tax_year(household, reference_tax_year)` once before the per-year `while True` loop begins, alongside the existing `deemed_owner = deemed_rmd_owner(household)` line; store the result for use every iteration (depends on T006)
- [X] T008 [US1] In the per-year loop, immediately after the existing `_member_gross_social_security_benefits()` call, determine `is_post_death = death_tax_year is not None and tax_year > death_tax_year`; when `True`, call `retirement_planner.mechanics.compute_survivor_benefit()` with the dying member's and surviving member's current `member_ss_benefits[...]` values (research.md Decisions 2-3), set the dying member's entry to `0.0` and the surviving member's entry to the result, recompute `household_ss_benefit` as that result, and extend this year's `figures_used` with `compute_survivor_benefit()`'s own `figures_used` (depends on T007)
- [X] T009 [US1] In the same loop, compute `effective_filing_status = "single" if is_post_death else household.filing_status` and use it in place of `household.filing_status` in this year's `compute_federal_tax()`, `compute_state_tax()`, `compute_irmaa_surcharge()`, and `compute_niit()` calls — `household.filing_status` itself is never mutated (depends on T007)
- [X] T010 [US1] In the same loop, compute `effective_spending_need = annual_spending_need * (1 - household.survivor_spending_reduction_pct) if is_post_death else annual_spending_need`, and pass it as `compute_plan_year_mechanics()`'s `spending_need` argument in place of the unconditional `annual_spending_need` (depends on T007)
- [X] T011 [US1] Populate the constructed `PlanYearProjection(...)`'s new `filing_status=effective_filing_status` and `effective_spending_need=effective_spending_need` fields for every plan year (depends on T003, T008, T009, T010)
- [X] T012 [US1] Update `run_plan_projection()`'s docstring to describe the new death-tax-year switch (filing status, Social Security, spending), per contracts/comparison-api.md (depends on T008, T009, T010, T011)

### Tests for User Story 1

- [X] T013 [P] [US1] Unit tests in `tests/unit/comparison/test_projection.py`: filing status is `married_filing_jointly` through the death year and `single` after (Acceptance Scenario 1); Social Security income equals `compute_survivor_benefit()`'s result from the year after death forward, with the deceased member's own entry at `0.0` (Acceptance Scenario 2); `annual_spending_need` unchanged when no reduction percentage is configured (Acceptance Scenario 3); `effective_spending_need` reduced by the configured percentage from the year after death forward (Acceptance Scenario 4) (depends on T008, T009, T010, T011)
- [X] T014 [P] [US1] Regression tests in `tests/unit/comparison/test_projection.py`: a household with no member's `predicted_death_age` configured produces output byte-for-byte identical to before this feature, every year (Acceptance Scenario 5, SC-002); a `"single"`-filing-status household is never affected by this feature's logic regardless of any `predicted_death_age` value present (Acceptance Scenario 6) (depends on T008, T009, T010, T011)
- [X] T015 [P] [US1] Edge-case unit tests in `tests/unit/comparison/test_projection.py`: `predicted_death_age` translating to a tax year before `start_tax_year` → single/survivor-benefit/reduced-spending for the entire horizon; translating to a tax year after the last plan year → no effect anywhere; both members configured → the earlier death year drives the switch, the survivor's own later configured death has no further effect; the death year itself → still `married_filing_jointly`, full combined Social Security, full spending (spec.md Edge Cases) (depends on T008, T009, T010, T011)
- [X] T016 [P] [US1] Monte Carlo regression test in `tests/unit/simulation/test_monte_carlo.py`: for a death-configured household and a fixed seed, `run_simulation()`'s per-path results reflect the identical deterministic switch `run_plan_projection()` produces directly for the same path's return sequence — confirms the switch propagates transitively through the existing shared call site with no probabilistic per-path death draw (FR-007, SC-005) (depends on T008, T009, T010, T011)

**Checkpoint**: User Story 1 fully functional and independently testable — SC-001, SC-002, SC-003 satisfied.

---

## Phase 4: User Story 2 - The strategy comparison layer reflects the same survivor scenario (Priority: P2)

**Goal**: Confirm every strategy-comparison candidate independently reflects the identical
mid-horizon switch, with zero comparison-layer code changes (research.md Decision 6).

**Independent Test**: Run a comparison with at least two candidates against a death-configured
household and confirm every candidate's post-death years show the switch (quickstart.md §3).

### Tests for User Story 2

- [X] T017 [US2] Integration test in `tests/unit/comparison/test_compare.py`: run `compare_withdrawal_sequencing_strategies()` (or another `compare_*()`) with at least two candidates against a death-configured household; confirm every candidate's post-death `PlanYearProjection.filing_status == "single"` and Social Security income equals the survivor-benefit amount, independently per candidate (Acceptance Scenario 1) (depends on T008, T009, T010, T011)
- [X] T018 [US2] Add a code comment in `comparison/compare.py` (or the new test's docstring) noting, per research.md Decision 6, that no production code change was needed here — every `compare_*()` function already forwards `household` unmodified into each candidate's own `run_plan_projection()` call (depends on T017)

**Checkpoint**: User Story 2 confirmed — SC-004 satisfied, zero new production code in `compare.py`.

---

## Phase 5: User Story 3 - The modeled behavior and its limits are documented (Priority: P3)

**Goal**: `docs/BRD.md` describes the mid-horizon filing-status switch, survivor Social Security
income, and spending-reduction assumption as modeled, alongside the honestly disclosed remaining
gaps.

**Independent Test**: Read `docs/BRD.md`'s Social Security / projection-engine section and confirm
it describes this feature's modeled behavior and its disclosed gaps (quickstart.md §4).

### Implementation for User Story 3

- [X] T019 [US3] Update `docs/BRD.md`'s Social Security / projection-engine section (the section `017` last touched) per research.md Decision 7: describe the mid-horizon filing-status switch, survivor Social Security income, and spending-reduction assumption as modeled behavior for deterministic and comparison projections; separately list the disclosed remaining gaps — Monte Carlo per-path wiring (FR-007), no Qualifying Surviving Spouse / MFJ-in-year-of-death status, no remarriage modeling, no detailed post-death budget re-plan beyond the single percentage, no handling of a second (survivor's own) configured death (depends on T012, T017)
- [X] T020 [US3] Run `specs/018-survivor-scenario-projection/quickstart.md`'s four snippets against the implemented code (interactively or as a scratch script) and confirm each prints/asserts the expected values (depends on T011, T017, T019)

**Checkpoint**: All three user stories independently functional — SC-006 satisfied.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mechanical ripple into the BFF and Streamlit UI packages (016 research.md Decision 6
precedent, reused by 017) so a real user can configure `survivor_spending_reduction_pct` through
the API or UI, not only via YAML or direct Python — not required for any user story's own
independent test.

- [X] T021 [P] Add `survivor_spending_reduction_pct: float = 0.0` to `HouseholdRequest` in `services/bff/src/rp_bff/schemas.py`, mirroring `Household` (contracts/scenario-api.md) (depends on T002)
- [X] T022 [P] Extend `services/bff/tests/unit/test_resolution.py` and/or `services/bff/tests/integration/test_bff_lifecycle.py` with a case round-tripping `survivor_spending_reduction_pct` through the API, following that suite's existing per-field pattern (depends on T021)
- [X] T023 [P] Add a household-level "Spending reduction after a spouse's death" input to `apps/streamlit_ui/pages/1_Scenarios.py` (shown when `filing_status == "married_filing_jointly"`): session-state default, load-from-scenario assignment, `st.number_input` widget, and inclusion in the saved-scenario payload dict — mirroring an existing optional-field input's pattern exactly (research.md Decision 6/7 precedent) (depends on T002)
- [X] T024 [P] Extend `apps/streamlit_ui/tests/integration/test_app_pages.py` with coverage for the new field, following that suite's existing per-field pattern (depends on T023)
- [X] T025 Run the full four-suite quality gate from CLAUDE.md/README.md: `pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`, `cd e2e && ../.venv/bin/python3.12 -m pytest -q` — confirm all green (depends on T001-T024)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user story phases.
- **User Story 1 (Phase 3)**: Depends on Foundational only. The MVP — delivers the entire
  observable behavior change (the widow's-tax-penalty switch itself).
- **User Story 2 (Phase 4)**: Depends on User Story 1's implementation (T008-T011) being complete —
  unlike `017`'s two genuinely-independent stories, US2 here has no implementation of its own to
  run ahead of US1; it only verifies US1's switch propagates into `compare_*()`.
- **User Story 3 (Phase 5)**: Depends on User Story 1 (T012) and User Story 2 (T017) — it documents
  both stories' completed behavior.
- **Polish (Phase 6)**: Depends on Foundational's T002 (the `Household` field) only — independent
  of Phases 3-5's own completion, but pointless to demo before at least Phase 3 lands.

### Within Each Phase

- Foundational: T002 and T003 in parallel; T004 and T005 both depend on T002.
- User Story 1: T006 → T007 → T008/T009/T010 (can be implemented as one combined edit to the same
  loop iteration, but are listed separately since each modifies a distinct existing call) → T011 →
  T012; then T013/T014/T015/T016 in parallel with each other.
- User Story 2: T017 → T018.
- User Story 3: T019 → T020.
- Polish: T021 → T022; T023 → T024 (parallel with the T021 chain); T025 last (depends on
  everything).

### Parallel Opportunities

- Foundational: T002 (`scenario/models.py`) and T003 (`comparison/models.py`) in parallel —
  different files.
- Within User Story 1: T013, T014, T015, and T016 in parallel once T008-T011 land (all four are
  test-only, largely against the same file but independent test functions).
- Within Polish: T021's chain (`services/bff/`) and T023's chain (`apps/streamlit_ui/`) in
  parallel — different packages entirely.
- **File-contention note**: T008, T009, T010, and T011 all edit the same per-year loop inside
  `run_plan_projection()` (`comparison/projection.py`) — sequence these rather than attempting them
  concurrently, unlike `017`'s two-story file-contention note (which was about two independent
  stories sharing a file); here it's one story's own tightly-coupled sequence.

---

## Parallel Example: User Story 1 (tests)

```bash
Task: "Unit tests for the pre/post-death split in tests/unit/comparison/test_projection.py (T013)"
Task: "Regression tests (no-death, single-filer) in tests/unit/comparison/test_projection.py (T014)"
Task: "Edge-case tests (early/late/both-configured/death-year-itself) in tests/unit/comparison/test_projection.py (T015)"
Task: "Monte Carlo propagation regression test in tests/unit/simulation/test_monte_carlo.py (T016)"
```

## Parallel Example: Polish

```bash
Task: "BFF schema + round-trip test for survivor_spending_reduction_pct (T021-T022)"
Task: "Streamlit UI input + test for survivor_spending_reduction_pct (T023-T024)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational) — the shared data-model fields.
2. Complete Phase 3 (User Story 1) — the death-tax-year switch is live in every deterministic
   projection.
3. **STOP and VALIDATE**: run `pytest tests/unit/comparison/test_projection.py
   tests/unit/simulation/test_monte_carlo.py` and confirm green. This alone delivers the entire
   observable "widow's tax penalty" capability (SC-001, SC-002, SC-003) that rp-g8y exists for.

### Incremental Delivery

1. Setup + Foundational → shared fields ready.
2. User Story 1 → the mid-horizon switch ships and takes effect in every deterministic and
   Monte Carlo-path-level projection — this is the deliverable with live projection impact.
3. User Story 2 → confirms (with zero new production code) that every strategy comparison
   candidate independently reflects the same switch.
4. User Story 3 → documentation/auditability catches up (`docs/BRD.md`).
5. Polish → BFF/Streamlit plumbing for `survivor_spending_reduction_pct` so a scenario can set it
   outside direct YAML/Python use, plus the full four-suite quality gate.

### Notes

- User Story 2 is intentionally the lightest phase in this task list — research.md Decision 6
  already established, by reading `compare.py`, that no comparison-layer code needs to change; T017
  exists to *prove* that empirically, not merely assert it, mirroring `017`'s own T020 precedent
  (a regression test proving non-interference, not just documenting an intention).
- T016 mirrors `016`'s and `017`'s own precedent (each added an explicit `test_monte_carlo.py`
  consistency check for the shared `run_plan_projection()` call site) — belt-and-suspenders, not
  because the underlying "every path already calls this function" reasoning is in doubt.
- Per this repo's Conservative git profile (CLAUDE.md): no task here commits, pushes, or opens a
  PR — that remains a separate, explicitly-requested step after implementation.
