---

description: "Task list for 027-nc-bailey-exclusion"
---

# Tasks: Source-Attributed Retirement Income for State Exclusions (NC Bailey Settlement)

**Input**: Design documents from `/specs/027-nc-bailey-exclusion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included — the constitution's "Unit test coverage for numeric primitives" gate and this
project's existing convention (every prior `tax/state/*` module ships tests before use) apply here.

**Organization**: Tasks are grouped by user story (spec.md) to enable independent implementation
and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project — `src/retirement_planner/`, `tests/unit/`, `tests/integration/` at repository root
(plan.md § Project Structure).

---

## Phase 1: Setup

No new project, dependency, or tooling setup is needed — this feature extends three existing,
already-configured subpackages. Phase skipped (matches 024-nc-state-tax's own precedent for a
similarly-scoped follow-on feature).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The additive data-model fields every user story's behavior and tests depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T001 [P] Add `bailey_qualifying: bool = False` field to `IncomeStream` in
      `src/retirement_planner/scenario/models.py` (data-model.md § IncomeStream), documented per
      contracts/scenario-api.md
- [X] T002 [P] Add `government_pension_income: float = 0.0` field to `IncomeComponents` in
      `src/retirement_planner/tax/models.py` (data-model.md § IncomeComponents), documented per
      contracts/tax-api.md
- [X] T003 Read optional `"bailey_qualifying"` key in `_build_income_stream()` in
      `src/retirement_planner/scenario/loader.py` (defaults to `False`, same discipline as
      `end_age`) — depends on T001
- [X] T004 [P] Round-trip `"bailey_qualifying"` in `_income_stream_to_dict()` in
      `src/retirement_planner/scenario/store.py` — depends on T001
- [X] T005 [P] Add scenario round-trip test coverage for `bailey_qualifying` (default `False` when
      omitted; `True` round-trips through `parse_scenario()`/save-load) in
      `tests/unit/scenario/test_loader.py` and `tests/unit/scenario/test_store.py` — depends on
      T001, T003, T004

**Checkpoint**: `IncomeStream.bailey_qualifying` and `IncomeComponents.government_pension_income`
exist, default to inert values, and round-trip correctly. No behavior change yet — every existing
test still passes unmodified.

---

## Phase 3: User Story 1 - A NC retiree with a Bailey-qualifying pension gets an accurate state tax result (Priority: P1) 🎯 MVP

**Goal**: NC's `compute_tax()` excludes Bailey-qualifying income from its taxable base; a
household's Bailey-qualifying pension stream flows through a full projection into that exclusion.

**Independent Test**: Configure a household with one member's pension income stream marked
Bailey-qualifying and state `"NC"`, run a projection for a documented tax year, and confirm the
computed NC state tax excludes that stream's amount from the taxable base.

- [X] T006 [P] [US1] Add Bailey exclusion unit tests to `tests/unit/tax/test_state_nc.py`: partial
      exclusion (spec.md Acceptance Scenario 1), full exclusion → $0 (Scenario 2), no
      `government_pension_income` set → unchanged from 024-nc-state-tax's original behavior
      (Scenario 3), and exclusion floored at $0 when `government_pension_income` would exceed
      `ordinary_income` (Edge Cases) — write before T007 so it fails first (quickstart.md § 1)
- [X] T007 [US1] Modify `compute_tax()` in `src/retirement_planner/tax/state/nc.py` to compute
      `taxable_base = max(0.0, income.ordinary_income - income.government_pension_income)` and run
      that through the existing `apply_progressive_brackets()` call (contracts/tax-api.md) —
      depends on T002, T006
- [X] T008 [US1] Update `src/retirement_planner/tax/state/nc.py`'s module docstring to document
      Bailey settlement support (citation: N.C. Gen. Stat. §105-134.6 history; *Bailey v. State of
      North Carolina*, 1998), replacing the prior "this module defines no Bailey handling"
      paragraph, and note why no new `SourcedFigure` was introduced (research.md §4) — depends on
      T007
- [X] T009 [US1] Add `_household_bailey_qualifying_income(household, ages_this_year, tax_year,
      reference_tax_year) -> float` private helper to
      `src/retirement_planner/comparison/projection.py`, mirroring `_member_earned_income_amounts()`'s
      filter-and-recompute shape, summing `compute_income_stream_amount()` across streams where
      `bailey_qualifying` is `True` (contracts/comparison-api.md, research.md §6) — depends on T001
- [X] T010 [US1] Call the new helper in `run_plan_projection()` (same loop iteration as the
      existing `_member_income_stream_amounts()` call) and pass its result as
      `government_pension_income=` into the existing `IncomeComponents(...)` construction in
      `src/retirement_planner/comparison/projection.py` (contracts/comparison-api.md) — depends on
      T002, T009
- [X] T011 [US1] Add a projection-level integration test (household with a Bailey-qualifying
      pension stream, state `"NC"`) asserting the computed `state_tax.state_tax_owed` excludes that
      stream's amount, in `tests/unit/comparison/test_projection.py` — depends on T007, T010
      (quickstart.md § 3)

**Checkpoint**: User Story 1 fully functional and independently testable — a NC household with a
Bailey-qualifying pension sees the real exemption applied end-to-end.

---

## Phase 4: User Story 2 - Federal tax, FICA, IRMAA, and NIIT still see the full pension income (Priority: P1)

**Goal**: Confirm, with a regression test, that marking a stream Bailey-qualifying changes nothing
outside NC's own state tax — federal tax, FICA, IRMAA MAGI, and NIIT all still see the full income.

**Independent Test**: Configure the household from User Story 1 and confirm federal tax, FICA,
IRMAA MAGI, and NIIT match a household with the same total ordinary income and no
`bailey_qualifying` flag set on any stream.

- [X] T012 [US2] Add a projection-level regression test in `tests/unit/comparison/test_projection.py`
      asserting `federal_tax`, `fica_tax`, `irmaa`, and `niit` are byte-for-byte identical between
      (a) a household with a Bailey-qualifying pension stream and (b) an otherwise-identical
      household with the same stream's income but `bailey_qualifying=False` — depends on T010 (no
      new production code; this story validates research.md §5's by-construction guarantee)

**Checkpoint**: User Story 1 and User Story 2 both pass — NC's exclusion is proven isolated to NC's
own state tax.

---

## Phase 5: User Story 3 - South Carolina, Delaware, and Florida results are unaffected (Priority: P2)

**Goal**: Confirm, with a regression test, that `bailey_qualifying` and `government_pension_income`
are inert outside NC — SC, DE, and FL compute identically with or without the flag set.

**Independent Test**: Run a household with a stream marked Bailey-qualifying against SC, DE, and FL
and confirm each state's computed tax is identical to the same household with no
`bailey_qualifying` flag set.

- [X] T013 [P] [US3] Add a test to `tests/unit/tax/test_state_sc.py`,
      `tests/unit/tax/test_state_de.py`, and `tests/unit/tax/test_state_fl.py` (or one shared
      parametrized test) asserting `compute_tax()`'s result is identical for an `IncomeComponents`
      with `government_pension_income` set vs. left at its `0.0` default, for the same
      `ordinary_income` — depends on T002
- [X] T014 [US3] Add a projection-level regression test in `tests/unit/comparison/test_projection.py`
      running the household from User Story 1 against `state="SC"`, `"DE"`, and `"FL"` and
      asserting each state's `state_tax.state_tax_owed` is unchanged from the same household with
      no stream marked `bailey_qualifying` — depends on T010

**Checkpoint**: All three user stories pass independently and together — `pytest tests/` is green.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T015 Update `docs/BRD.md` §5.4's North Carolina row to record Bailey-settlement support (and,
      if §5.4 lists a verification status per mechanism, note the exclusion mechanism is a cited
      structural rule rather than a `SourcedFigure` — research.md §4) (spec.md FR-008)
- [X] T016 Run `pytest tests/` in full and confirm zero Bailey-specific special-casing exists
      outside `scenario/models.py`, `scenario/loader.py`, `scenario/store.py`, `tax/models.py`,
      `tax/state/nc.py`, and `comparison/projection.py` (spec.md SC-004)

---

## Dependencies & Execution Order

- **Phase 2 (Foundational)** blocks every user story — T001-T005 must complete first.
- **User Story 1 (Phase 3, P1)** depends only on Phase 2. Delivers the MVP: real Bailey exclusion,
  end-to-end from scenario config to NC tax result.
- **User Story 2 (Phase 4, P1)** depends on Phase 3 (T010, the `IncomeComponents` wiring) — it adds
  regression coverage for behavior Phase 3's design already guarantees; no new production code.
- **User Story 3 (Phase 5, P2)** depends on Phase 2 (T013) and Phase 3 (T014) — independent of
  Phase 4.
- **Phase 6 (Polish)** depends on Phases 3-5 being complete.

```text
Phase 2 (Foundational)
  ├── Phase 3 (US1, P1) — MVP
  │     └── Phase 4 (US2, P1)
  └── Phase 5 (US3, P2) [T013 only needs Phase 2; T014 needs Phase 3 too]
Phase 6 (Polish) — after 3, 4, 5
```

## Parallel Execution Examples

Within Phase 2, T001, T002, T004, T005 (once its own deps land) can run in parallel — different
files (`scenario/models.py`, `tax/models.py`, `scenario/store.py`, test files); T003 depends on
T001 landing first.

Within Phase 3, T006 (tests) can be written in parallel with T009 (the projection helper) — both
depend only on Phase 2, not on each other — before T007/T008/T010/T011 wire them together.

Within Phase 5, T013's three state test files can be edited in parallel with each other and with
T014.

## Implementation Strategy

**MVP = User Story 1 (Phase 2 + Phase 3)**: delivers the entire user-facing value (an accurate NC
Bailey exclusion) and is independently testable via `tests/unit/tax/test_state_nc.py` and
`tests/unit/comparison/test_projection.py` alone. User Stories 2 and 3 add regression-safety
coverage for guarantees the Phase 3 design already provides by construction (research.md §5, §1) —
valuable to merge before calling the feature done (spec.md SC-002/SC-003), but not blocking a
demo of the core capability.
