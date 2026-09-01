---

description: "Task list for 019-roth-conversion-ladder"
---

# Tasks: Roth Conversion Ladder (Five-Year Rule) Tracking

**Input**: Design documents from `/specs/019-roth-conversion-ladder/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The constitution's "Unit test coverage for numeric primitives" gate
(Development Workflow & Quality Gates) and this project's existing precedent (016, 017, 018)
require new engine behavior to have unit tests against hand-calculated/reference values before
it's used in any comparative run.

**Organization**: Tasks are grouped by user story (spec.md), but unlike `017`/`018`, User Stories 1
and 2 here share a single underlying implementation — `compute_roth_ladder_consumption()`'s
oldest-lot-first attribution algorithm (research.md Decisions 3-5) already handles both the
single-lot flag case (US1) and the multi-lot ordering case (US2) in one function, built once in
Foundational. US1's phase wires that function into a running projection (the only production-code
change needed for either story); US2's phase is multi-lot test coverage of behavior the same
function already provides, mirroring `018`'s own "a later story can be test-only" precedent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project — `src/retirement_planner/`, `tests/` at repo root. No `services/bff/` or
`apps/streamlit_ui/` changes this feature (plan.md Summary — no new scenario-configurable input).

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before changing shared code.

- [X] T001 Run `pytest tests/` and confirm the existing suite is green before any change in this feature (baseline for regression comparison later)

**Checkpoint**: Baseline confirmed green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared lot-tracking types and the one consumption function both user stories'
tests exercise — data-model.md's `RothConversionLot`/`RothLadderConsumptionResult` and
contracts/mechanics-api.md's `compute_roth_ladder_consumption()`.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `RothConversionLot` (`conversion_tax_year: int`, `balance: float`) and `RothLadderConsumptionResult` (`updated_lots: list[RothConversionLot]`, `unseasoned_amount_flagged: float`, `figures_used: list[FigureUsage] = field(default_factory=list)`) dataclasses to `src/retirement_planner/mechanics/models.py`, per data-model.md and contracts/mechanics-api.md
- [X] T003 [US1] Create `src/retirement_planner/mechanics/roth_conversion_ladder.py`: module docstring (per plan.md's "new sibling module" rationale, research.md Decision 1) plus `ROTH_CONVERSION_SEASONING_YEARS: SourcedFigure[int]` (`schedule={year: 5 for year in _DOCUMENTED_YEARS}`; citation "26 U.S.C. §408A(d)(3)(F); Treas. Reg. §1.408A-6, Q&A-5"; cross-check the regulation text directly before setting `verified=True`, per the constitution's verified-figure gate) (depends on T002)
- [X] T004 [US1] In the same file, implement `compute_roth_ladder_consumption(lots, non_lot_roth_balance, roth_draw_amount, tax_year, age_condition_active) -> RothLadderConsumptionResult`: attribute `roth_draw_amount` across `non_lot_roth_balance` first (unlimited, never flagged), then across `lots` sorted oldest-`conversion_tax_year`-first, never touching a newer lot while an older one has a positive balance (FR-004); a lot is seasoned once `tax_year - lot.conversion_tax_year >= ROTH_CONVERSION_SEASONING_YEARS.value_for_year(tax_year)` (FR-003); `unseasoned_amount_flagged` sums every dollar drawn from a not-yet-seasoned lot only when `age_condition_active` is `True` (FR-005/FR-006); pure — returns a fresh `updated_lots` list, never mutates the `lots` argument (research.md Decision 5); `figures_used` carries the figure's usage whenever `roth_draw_amount > non_lot_roth_balance` regardless of the resulting flag (research.md Decision 4); raises `UnsupportedTaxYearError` per contracts/mechanics-api.md (depends on T003)
- [X] T005 [US1] Re-export `compute_roth_ladder_consumption`, `RothConversionLot`, `RothLadderConsumptionResult`, and `ROTH_CONVERSION_SEASONING_YEARS` from `src/retirement_planner/mechanics/__init__.py` (depends on T002, T004)

**Checkpoint**: The pure consumption function exists, cited, and exported. User story implementation can now begin.

---

## Phase 3: User Story 1 - A projection flags an unseasoned Roth conversion withdrawal (Priority: P1) 🎯 MVP

**Goal**: A plan year's withdrawal that reaches into a not-yet-seasoned Roth conversion, while at
least one household member is 59 or younger, is flagged on that plan year's output.

**Independent Test**: Configure a household with a conversion window ending years before any
member turns 60, followed by a withdrawal need large enough to draw past the pre-existing Roth
balance into the conversion, and confirm the flagged plan year names the amount (quickstart.md §1);
confirm once seasoned or once every member is 60+, no flag is raised (quickstart.md §2); confirm a
household with no Roth conversion at all is byte-for-byte unaffected (quickstart.md §3).

### Implementation for User Story 1

- [X] T006 [US1] Add `unseasoned_roth_withdrawal: float = 0.0` to `PlanYearProjection` in `src/retirement_planner/comparison/models.py`, per data-model.md and contracts/comparison-api.md
- [X] T007 [US1] In `run_plan_projection()` (`src/retirement_planner/comparison/projection.py`), declare `roth_conversion_lots: list[RothConversionLot] = []` as local state before the per-year `while True` loop begins — never a function parameter (research.md Decision 2) (depends on T002)
- [X] T008 [US1] In the per-year loop, immediately after `mechanics_result = compute_plan_year_mechanics(...)`: compute `roth_draw_amount` from the `"roth"`-type entry in `mechanics_result.withdrawal_plan.sequence_withdrawals` (0.0 if none); compute `non_lot_roth_balance` as `current_balances.roth` minus the sum of every lot's own `balance`, clamped to `>= 0.0`; compute `age_condition_active = any(age <= 59 for age in ages_this_year.values())` (contracts/comparison-api.md steps 1-3) (depends on T004, T007)
- [X] T009 [US1] Immediately after T008: call `compute_roth_ladder_consumption(roth_conversion_lots, non_lot_roth_balance, roth_draw_amount, tax_year, age_condition_active)`; reassign `roth_conversion_lots = ladder_result.updated_lots`; fold `ladder_result.figures_used` into this year's overall `figures_used` list (contracts/comparison-api.md step 4) (depends on T008)
- [X] T010 [US1] Immediately after T009: if `mechanics_result.conversion.amount_converted > 0`, append `RothConversionLot(conversion_tax_year=tax_year, balance=mechanics_result.conversion.amount_converted)` to `roth_conversion_lots` — after, never before, T009's consumption call (contracts/comparison-api.md step 5, spec.md Edge Cases) (depends on T009)
- [X] T011 [US1] Populate the constructed `PlanYearProjection(...)`'s new `unseasoned_roth_withdrawal=ladder_result.unseasoned_amount_flagged` field for every plan year (depends on T006, T009)
- [X] T012 [US1] Update `run_plan_projection()`'s docstring to describe the new lot-tracking/flagging behavior, per contracts/comparison-api.md (depends on T008, T009, T010, T011)

### Tests for User Story 1

- [X] T013 [P] [US1] Unit tests for `compute_roth_ladder_consumption()` in `tests/unit/mechanics/test_roth_conversion_ladder.py`: a draw fully within `non_lot_roth_balance` never flags, regardless of lot ages (Acceptance Scenario US1.4); a draw into an unseasoned lot with `age_condition_active=True` flags exactly the amount drawn from that lot (Acceptance Scenario US1.1); the identical draw at `tax_year` 5+ years past the lot's own conversion year never flags (Acceptance Scenario US1.2, seasoned); the identical draw with `age_condition_active=False` never flags (Acceptance Scenario US1.3); `figures_used` is empty when the draw never reaches a lot, populated when it does regardless of the flag outcome (research.md Decision 4); `UnsupportedTaxYearError` for an undocumented tax year; the returned `updated_lots` is a new list/instances, the `lots` argument passed in is untouched (research.md Decision 5, purity) (depends on T004)
- [X] T014 [P] [US1] Integration tests in `tests/unit/comparison/test_projection.py`: a household with one conversion and a later withdrawal reaching into it while under 59.5 → that plan year's `unseasoned_roth_withdrawal` is positive and the conversion year itself is 0.0 (Acceptance Scenario 1, quickstart.md §1); once seasoned or once every member is 60+, `unseasoned_roth_withdrawal` is 0.0 for every later year regardless of draw amount (Acceptance Scenarios 2-3, quickstart.md §2); a household with `conversion_strategy=None` (no conversion configured) → `unseasoned_roth_withdrawal` is 0.0 for every plan year, and every other field is byte-for-byte identical to a projection with `compute_roth_ladder_consumption()` never having been touched (FR-008, SC-004, quickstart.md §3) (depends on T011)
- [X] T015 [P] [US1] Regression test in `tests/unit/comparison/test_projection.py` (or `test_compare.py`): confirm no existing projection's reported spending, tax, shortfall, or ending-balance figures change because of this feature — run one existing conversion-bearing fixture before/after asserting only `unseasoned_roth_withdrawal` differs from a hand-built expectation, every other field matches the pre-feature value (FR-007, SC-005) (depends on T011)
- [X] T016 [P] [US1] Monte Carlo regression test in `tests/unit/simulation/test_monte_carlo.py`: a death-free household with a conversion ladder configured, run through `run_simulation()`, produces per-path `unseasoned_roth_withdrawal` values identical to a direct `run_plan_projection()` call for the same path's return sequence — confirms the feature's purely-local state propagates transitively with no cross-path leakage (research.md Decision 2, contracts/mechanics-api.md's "zero simulation-package changes" claim) (depends on T011)

**Checkpoint**: User Story 1 fully functional and independently testable — SC-001, SC-002, SC-004, SC-005 satisfied.

---

## Phase 4: User Story 2 - Multiple conversions season and draw down independently, oldest first (Priority: P2)

**Goal**: Confirm a draw that reaches into converted principal is apportioned to the oldest
unexhausted lot first, across lots of different ages and seasoning states — behavior
`compute_roth_ladder_consumption()` (Foundational) already implements; this phase is dedicated
multi-lot test coverage of it, plus one end-to-end confirmation through a real projection.

**Independent Test**: Configure two conversions of different amounts in different tax years,
followed by a withdrawal that only partially reaches into converted principal, and confirm the
older lot is drawn down first (quickstart.md's pattern extended to two lots).

### Tests for User Story 2

- [X] T017 [P] [US2] Unit tests for `compute_roth_ladder_consumption()` multi-lot ordering in `tests/unit/mechanics/test_roth_conversion_ladder.py`: two unseasoned lots ($20,000 at year Y, $15,000 at year Y+2) — a $10,000 draw past `non_lot_roth_balance` is sourced entirely from the Y lot, leaving Y+2 untouched (Acceptance Scenario US2.1); a $25,000 draw exhausts the Y lot ($20,000) and draws the remaining $5,000 from the Y+2 lot (Acceptance Scenario US2.2); with the Y lot now seasoned but Y+2 still unseasoned, only the portion of a draw sourced from Y+2 is flagged — a draw staying within the seasoned Y lot's amount is not (Acceptance Scenario US2.3) (depends on T004)
- [X] T018 [US2] Integration test in `tests/unit/comparison/test_projection.py`: a household with two conversions executed in different plan years, followed by a withdrawal reaching past the first (older) lot into the second, confirms `unseasoned_roth_withdrawal` reflects only the portion actually sourced from the still-unseasoned newer lot once the older one has separately seasoned — end-to-end confirmation that `run_plan_projection()`'s oldest-lot-first reassignment (T009-T010) matches the pure function's own ordering (depends on T009, T010, T011, T017)

**Checkpoint**: User Story 2 confirmed — SC-003 satisfied.

---

## Phase 5: User Story 3 - The rule and its limits are documented and auditable (Priority: P3)

**Goal**: The 5-year seasoning figure carries a citation/verification trail like every other
regulated figure in this codebase; `docs/BRD.md` describes the new modeled behavior and its
disclosed gaps.

**Independent Test**: Inspect `ROTH_CONVERSION_SEASONING_YEARS`'s `FigureUsage` output and confirm
it carries its statutory citation and a `last_verified` date; read `docs/BRD.md`'s Roth conversion
section and confirm it describes the new behavior and remaining gaps (quickstart.md §4).

### Implementation for User Story 3

- [X] T019 [P] [US3] Add a citation-content assertion to `tests/unit/mechanics/test_roth_conversion_ladder.py`: a `RothLadderConsumptionResult.figures_used` entry named `roth_conversion_seasoning_years` carries the expected citation text, a `last_verified` date, and `verified is True` (depends on T003, T013)
- [X] T020 [US3] Update `docs/BRD.md` per research.md Decision 6: extend `§6.6 Roth conversion & withdrawal sequencing` to describe conversion-lot seasoning tracking and the unseasoned-withdrawal flag as modeled behavior (citing `26 U.S.C. §408A(d)(3)(F)`); add a bullet to `§7 Known Limitations & Open Items` disclosing the remaining gaps — no penalty dollar amount computed (tracked separately, rp-8z0), no per-member Roth ownership attribution, no modeling of the separate account-level Roth-earnings qualified-distribution rule (depends on T009, T010, T011)
- [X] T021 [US3] Run `specs/019-roth-conversion-ladder/quickstart.md`'s four snippets against the implemented code (interactively or as a scratch script) and confirm each prints/asserts the expected values (depends on T011, T018, T020)

**Checkpoint**: All three user stories independently functional — SC-006 satisfied.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Confirm the whole project's quality gate is unaffected — this feature touches no
`services/bff` or `apps/streamlit_ui` code (plan.md Summary), but the full four-suite gate is still
run as this project's standard completion check (016/017/018 precedent).

- [X] T022 Run the full four-suite quality gate from CLAUDE.md/README.md: `pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`, `cd e2e && ../.venv/bin/python3.12 -m pytest -q` — confirm all green (depends on T001-T021)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user story phases.
- **User Story 1 (Phase 3)**: Depends on Foundational only. The MVP — delivers the entire
  observable behavior change (the flag itself, for the common single-conversion case).
- **User Story 2 (Phase 4)**: Depends on Foundational (the multi-lot ordering it tests is already
  implemented there) and on User Story 1's wiring (T009-T011) for its one integration test (T018)
  — otherwise independent of Phase 3's own completion.
- **User Story 3 (Phase 5)**: Depends on Foundational (T003 for T019) and on User Story 1
  (T009-T011 for T020's BRD description of actually-wired behavior) — T018 (US2) also feeds T021's
  quickstart run.
- **Polish (Phase 6)**: Depends on everything (T001-T021).

### Within Each Phase

- Foundational: T002 (parallel with nothing else in this phase); T003 → T004 → T005.
- User Story 1: T006 (parallel with T007); T007 → T008 → T009 → T010 → T011 → T012; then
  T013/T014/T015/T016 in parallel with each other once T011 lands.
- User Story 2: T017 (parallel with User Story 1's own tests, once T004 lands); T018 depends on
  both T017 and User Story 1's T009-T011.
- User Story 3: T019 depends on T003/T013; T020 depends on User Story 1's T009-T011; T021 depends
  on T011, T018, T020.
- Polish: T022 last.

### Parallel Opportunities

- Foundational: T002 has no dependency on T003/T004/T005's own chain (different concern — plain
  dataclasses vs. the function/figure) and can proceed in parallel with starting T003, though T004
  itself still needs T002's types.
- Within User Story 1: T006 (`comparison/models.py`) and T007 (`comparison/projection.py`'s local
  declaration) touch different files and can proceed in parallel; T013-T016 in parallel with each
  other once T011 lands.
- Within User Story 2: T017 can start as soon as Foundational (T004) lands, independent of User
  Story 1's own progress — only T018 (the integration test) needs User Story 1's wiring.
- **File-contention note**: T007, T008, T009, T010, and T011 all edit the same per-year loop inside
  `run_plan_projection()` (`comparison/projection.py`) — sequence these rather than attempting them
  concurrently, mirroring `018`'s own analogous file-contention note for its per-year loop changes.

---

## Parallel Example: User Story 1 (tests)

```bash
Task: "Unit tests for compute_roth_ladder_consumption() in tests/unit/mechanics/test_roth_conversion_ladder.py (T013)"
Task: "Integration tests for the flag in a real projection in tests/unit/comparison/test_projection.py (T014)"
Task: "No-numeric-regression test in tests/unit/comparison/test_projection.py or test_compare.py (T015)"
Task: "Monte Carlo propagation regression test in tests/unit/simulation/test_monte_carlo.py (T016)"
```

## Parallel Example: Foundational + User Story 2 (once Foundational's T004 lands)

```bash
Task: "Wire the flag into run_plan_projection() (User Story 1, T006-T012)"
Task: "Multi-lot ordering unit tests against compute_roth_ladder_consumption() directly (User Story 2, T017)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational) — the pure consumption function, cited and
   exported.
2. Complete Phase 3 (User Story 1) — the flag is live in every deterministic and Monte Carlo-path
   projection.
3. **STOP and VALIDATE**: run `pytest tests/unit/mechanics/test_roth_conversion_ladder.py
   tests/unit/comparison/test_projection.py tests/unit/simulation/test_monte_carlo.py` and confirm
   green. This alone delivers the entire observable capability (SC-001, SC-002, SC-004, SC-005) rp-886
   exists for — a Roth conversion ladder's own seasoning is finally visible in this tool's output.

### Incremental Delivery

1. Setup + Foundational → the pure attribution algorithm ready, cited.
2. User Story 1 → the flag ships and takes effect in every projection immediately — this is the
   deliverable with live projection impact.
3. User Story 2 → confirms (mostly via already-built-in behavior) that multiple lots of different
   ages are apportioned correctly, oldest first.
4. User Story 3 → documentation/auditability catches up (`docs/BRD.md`).
5. Polish → the full four-suite quality gate, confirming zero regression to packages this feature
   doesn't touch at all.

### Notes

- Unlike `011`/`012`, this feature needs no BFF/Streamlit UI polish phase at all — plan.md's
  Summary and research.md Decision 2 establish there is no new scenario-configurable input to
  mirror there.
- T015/T016 mirror `017`'s/`018`'s own precedent of an explicit regression/consistency guard for a
  shared call site, even after confirming by design that the feature is purely additive — belt-and-
  suspenders, not because the underlying "no dollar amount changes" reasoning (FR-007, SC-005) is
  in doubt.
- Per this repo's Conservative git profile (CLAUDE.md): no task here commits, pushes, or opens a
  PR — that remains a separate, explicitly-requested step after implementation.
