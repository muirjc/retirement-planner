---

description: "Task list for 017-ss-spousal-survivor-benefits"
---

# Tasks: Social Security Spousal and Survivor Benefits

**Input**: Design documents from `/specs/017-ss-spousal-survivor-benefits/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The constitution's "Unit test coverage for numeric primitives" gate
(Development Workflow & Quality Gates) requires each new figure-driven calculation to have unit
tests against hand-calculated reference values before it's used in any comparative run.

**Organization**: Tasks are grouped by user story (spec.md) to enable independent implementation
and testing of each story. Unlike `016`, User Stories 1 and 2 here are genuinely independent of
each other (spec.md's own scoping: spousal floor needs no mortality concept at all; survivor
benefit + the data-model field are deliberately unwired) — there is no shared calculation primitive
both depend on, only a shared *file* (`mechanics/social_security_benefit.py`) they both happen to
extend. See the file-contention note under Parallel Opportunities.

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

**Purpose**: The shared result-type scaffolding both user stories' implementation tasks import.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `SpousalBenefitResult` (`spousal_amount: float`, `adjustment_factor: float`, `figures_used: list[FigureUsage]`) and `SurvivorBenefitResult` (`survivor_benefit: float`, `figures_used: list[FigureUsage]`) dataclasses to `src/retirement_planner/mechanics/models.py`, per data-model.md and contracts/mechanics-api.md

**Checkpoint**: Shared result types exist. User story implementation can now begin.

---

## Phase 3: User Story 1 - A lower-earning spouse's benefit is never less than the spousal floor (Priority: P1) 🎯 MVP

**Goal**: In an MFJ household, a member's Social Security income is raised to up to 50% of the
other member's PIA (reduced for the claiming member's own early claiming, never increased for
delayed claiming) whenever that's more than their own claiming-age-adjusted benefit — in every
projection, immediately, with no mortality/timeline concept needed.

**Independent Test**: Configure an MFJ household where one member's PIA is well under 50% of the
other's, run a plain projection, and confirm the lower-earning member's benefit reflects the
spousal floor (quickstart.md §1); confirm a household using this repo's existing ~$32k/$24k
reference pair is unaffected (quickstart.md §2).

### Implementation for User Story 1

- [X] T003 [US1] In `src/retirement_planner/mechanics/social_security_benefit.py`, add a private `_SpousalAdjustmentRates` dataclass (`early_reduction_rate_tier_1` = 25/36 of 1%, `early_reduction_rate_tier_2` = 5/12 of 1%, `early_reduction_tier_1_months` = 36) and `SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT: SourcedFigure[_SpousalAdjustmentRates]` (citation 42 U.S.C. §402(b)/(c); 20 C.F.R. §404.410's wife's/husband's-benefit paragraph; cross-check the regulation text directly before setting `verified=True`, per the constitution's verified-figure gate), per data-model.md and research.md Decision 2 (depends on T002)
- [X] T004 [US1] In the same file, add `compute_spousal_benefit_floor(other_member_pia, full_retirement_age, claiming_age, tax_year) -> SpousalBenefitResult`: `spousal_amount == 0.5 * other_member_pia` and `adjustment_factor == 1.0` for `claiming_age >= full_retirement_age` (no delayed credit, ever); the tiered spousal early-reduction formula below that; raises `UnsupportedTaxYearError` per contracts/mechanics-api.md (depends on T003)
- [X] T005 [US1] Re-export `compute_spousal_benefit_floor` and `SpousalBenefitResult` from `src/retirement_planner/mechanics/__init__.py` (depends on T004)
- [X] T006 [US1] Modify `_member_gross_social_security_benefits()` in `src/retirement_planner/comparison/projection.py`: after the existing per-member loop computes each member's own claiming-age-adjusted benefit, for a `"married_filing_jointly"` household once **both** members have individually reached their own claiming age this plan year (research.md Decision 3), call `compute_spousal_benefit_floor()` for each such member using the *other* member's raw `ss_annual_benefit` as `other_member_pia` and this member's own resolved `full_retirement_age`/`claiming_ages[...]`; set that member's benefit to `max(own_benefit, spousal_amount)`; extend `figures_used` with the spousal result's `figures_used` (depends on T004, T005)
- [X] T007 [US1] Update `_member_gross_social_security_benefits()`'s docstring to describe the new spousal-floor step (depends on T006)

### Tests for User Story 1

- [X] T008 [P] [US1] Unit tests for `compute_spousal_benefit_floor()` in `tests/unit/mechanics/test_social_security_benefit.py`: exactly 50% of the other's PIA at/after FRA (`adjustment_factor == 1.0`); a 24-month-early (tier-1-only) reduction case; a 60-month-early (both-tier) reduction case (spec.md Acceptance Scenario 3); claiming well after FRA still capped at exactly 50% (no delayed credit); `UnsupportedTaxYearError` for an undocumented tax year (depends on T004)
- [X] T009 [P] [US1] Integration tests in `tests/unit/comparison/test_projection.py`: an MFJ household with lower PIA well under 50% of the higher → lower member's benefit raised to the floor once both have claimed (Acceptance Scenario 1); the higher earner's own benefit unaffected (Acceptance Scenario 2); an MFJ household using this repo's existing ~$32k/$24k reference pair → output unchanged (regression, SC-002, research.md Decision 5); a `"single"`-filing-status household → no spousal logic invoked, output unchanged (Acceptance Scenario 4, FR-004); the floor does not apply until **both** members have individually reached their own claiming age (research.md Decision 3) (depends on T006)
- [X] T010 [P] [US1] Monte Carlo consistency test in `tests/unit/simulation/test_monte_carlo.py`: an MFJ household with a PIA disparity large enough to trigger the spousal floor, run through `run_simulation()`, produces the identical spousal-floor-adjusted benefit `run_plan_projection()` produces directly for a fixed seed — a regression guard against the shared call site (research.md Decision 7) ever drifting apart, mirroring 016's own `test_monte_carlo.py` consistency check for the same call site (depends on T006)

**Checkpoint**: User Story 1 fully functional and independently testable — SC-001, SC-002 satisfied.

---

## Phase 4: User Story 2 - Survivor benefit calculation is available and correct (Priority: P2)

**Goal**: A correct, cited survivor-benefit calculation exists, and `HouseholdMember` can record a
hypothetical death — without either being consulted by any running projection (`rp-g8y`'s scope).

**Independent Test**: Given two benefit amounts, `compute_survivor_benefit()` returns exactly the
higher one (quickstart.md §3); a scenario can set `predicted_death_age` with zero effect on any
existing computation (quickstart.md §4).

### Implementation for User Story 2

- [X] T011 [US2] In `src/retirement_planner/mechanics/social_security_benefit.py`, add `SS_SURVIVOR_BENEFIT_RULE: SourcedFigure[None]` (citation 42 U.S.C. §402(e)/(f); 20 C.F.R. §404.335/§404.336; `schedule={year: None for year in _DOCUMENTED_YEARS}`; cross-check the regulation text directly before setting `verified=True`), per data-model.md (depends on T002; touches the same file as T003/T004 — see Parallel Opportunities note)
- [X] T012 [US2] In the same file, add `compute_survivor_benefit(member_a_benefit, member_b_benefit, tax_year) -> SurvivorBenefitResult`: `survivor_benefit = max(member_a_benefit, member_b_benefit)`; `figures_used` cites `SS_SURVIVOR_BENEFIT_RULE`; raises `UnsupportedTaxYearError` per contracts/mechanics-api.md — no "which member died" parameter, since the result is symmetric in its two inputs (research.md Decision 4) (depends on T011)
- [X] T013 [US2] Re-export `compute_survivor_benefit` and `SurvivorBenefitResult` from `src/retirement_planner/mechanics/__init__.py` (depends on T012)
- [X] T014 [P] [US2] Add `predicted_death_age: int | None = None` to `HouseholdMember` in `src/retirement_planner/scenario/models.py`, with a docstring noting it's a hypothetical, opt-in, for-planning-purposes input consulted by nothing in this feature (data-model.md, research.md Decision 6)
- [X] T015 [US2] Parse the optional `predicted_death_age` field (int, default `None`) in `_build_household_member()` in `src/retirement_planner/scenario/loader.py`, mirroring the existing `hdhp_coverage` optional-field pattern (depends on T014). **Scope discovered during implementation**: `scenario/store.py`'s `_scenario_to_dict()` builds its YAML dict field-by-field and initially omitted `predicted_death_age` the same way it once omitted `full_retirement_age`/`hdhp_coverage` (016/010) — caught by a real BFF save/read round-trip test (T026) exactly as those two were; fixed here plus a dedicated `tests/unit/scenario/test_store.py` round-trip regression test, mirroring `test_full_retirement_age_survives_a_save_load_round_trip`'s own precedent. Neither `plan.md` nor `data-model.md` named `store.py` as a file this feature touches — noted here as the correction.
- [X] T016 [US2] Add two new rules to `_validate_household()` in `src/retirement_planner/scenario/validation.py`: **blocking** when `predicted_death_age < current_age` (incoherent); **warning** when a non-`None` `predicted_death_age` falls outside `[50, 110]` (implausible — reuses `simulation/survival_data.py`'s own age range), per data-model.md (depends on T014)

### Tests for User Story 2

- [X] T017 [P] [US2] Unit tests for `compute_survivor_benefit()` in `tests/unit/mechanics/test_social_security_benefit.py`: returns the higher of the two amounts regardless of argument order; a tie returns that shared value (SC-003); `figures_used` cites `ss_survivor_benefit_rule`; `UnsupportedTaxYearError` for an undocumented tax year (depends on T012)
- [X] T018 [P] [US2] Unit tests for `predicted_death_age` parsing in `tests/unit/scenario/test_loader.py`: YAML omitting it resolves to `None`; YAML providing a value round-trips unchanged (depends on T015)
- [X] T019 [P] [US2] Unit tests for the two new validation rules in `tests/unit/scenario/test_validation.py`: a value below `current_age` → one blocking flag; a value outside `[50, 110]` but `>= current_age` → one warning flag; a value inside the plausible range → no flag; `None` → no flag (depends on T016)
- [X] T020 [US2] Add a regression test (in `tests/unit/comparison/test_projection.py` or `tests/unit/scenario/test_models.py`) confirming no existing call site invokes `compute_survivor_benefit()` or reads `predicted_death_age` — e.g. by asserting a `predicted_death_age`-bearing scenario's projection output is byte-for-byte identical to the same scenario without it (FR-007) (depends on T012, T014)

**Checkpoint**: User Story 2 fully functional and independently testable — SC-003 satisfied;
confirmed not wired into any running projection (FR-007).

---

## Phase 5: User Story 3 - The new rules are documented and auditable (Priority: P3)

**Goal**: Both new figures carry the same citation/verification trail as every other regulated
figure in this codebase; `docs/BRD.md` describes the new modeled behavior and honestly discloses
what's still out of scope.

**Independent Test**: Inspect both figures' `FigureUsage` output and confirm each carries its
statutory citation and a `last_verified` date; read `docs/BRD.md`'s Social Security sections and
confirm they describe the new behavior and its remaining gaps (quickstart.md §5/§6).

### Implementation for User Story 3

- [X] T021 [P] [US3] Add a citation-content assertion to `tests/unit/mechanics/test_social_security_benefit.py`: a computed `SpousalBenefitResult.figures_used` entry named `ss_spousal_claiming_age_adjustment_rates` carries the expected citation text, a `last_verified` date, and `verified is True` (depends on T003, T008)
- [X] T022 [P] [US3] Add the equivalent citation-content assertion for `ss_survivor_benefit_rule` (depends on T011, T017)
- [X] T023 [US3] Update `docs/BRD.md` per data-model.md's "Modified: docs/BRD.md" section: §5.3's spousal/survivor bullet rewritten (spousal floor now modeled and wired; survivor-benefit calculation available but not yet wired, tracked as `rp-g8y`; family maximum benefit and deemed-filing mechanics named as the remaining, disclosed gaps); §6.2a's closing "Explicitly not modeled" paragraph drops spousal/survivor benefits and gains a new subsection describing both formulas and their citations (depends on T006, T012)
- [X] T024 [US3] Run `specs/017-ss-spousal-survivor-benefits/quickstart.md`'s six snippets against the implemented code (interactively or as a scratch script) and confirm each prints/asserts the expected values (depends on T006, T012, T014, T023)

**Checkpoint**: All three user stories independently functional — SC-005 satisfied.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mechanical ripple into the BFF and Streamlit UI packages (research.md Decision 6
precedent) so a real user can configure `predicted_death_age` through the API or UI, not only via
YAML or direct Python — not required for either user story's own independent test.

- [X] T025 [P] Add `predicted_death_age: int | None = None` to `HouseholdMemberRequest` in `services/bff/src/rp_bff/schemas.py`, mirroring `HouseholdMember` (contracts/scenario-api.md) (depends on T014)
- [X] T026 [P] Extend `services/bff/tests/unit/test_resolution.py` and/or `services/bff/tests/integration/test_bff_lifecycle.py` with a case round-tripping `predicted_death_age` through the API, following that suite's existing per-field pattern (depends on T025)
- [X] T027 [P] Add a "Predicted death age" input to `apps/streamlit_ui/pages/1_Scenarios.py` for both household member slots: session-state default, load-from-scenario assignment, `st.number_input` widget, and inclusion in the saved-scenario payload dict — mirroring the existing `full_retirement_age` pattern exactly (research.md Decision 6 precedent) (depends on T014)
- [X] T028 [P] Extend `apps/streamlit_ui/tests/integration/test_app_pages.py` with coverage for the new field, following that suite's existing per-field pattern (depends on T027)
- [X] T029 Run the full four-suite quality gate from CLAUDE.md/README.md: `pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`, `cd e2e && ../.venv/bin/python3.12 -m pytest -q` — confirm all green (depends on T001-T028)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS both user story phases.
- **User Story 1 (Phase 3)**: Depends on Foundational only. The MVP — delivers the fix rp-52n's
  largest gap exists for, with no dependency on Phase 4.
- **User Story 2 (Phase 4)**: Depends on Foundational only — independent of Phase 3, except that
  T011 shares a file (`mechanics/social_security_benefit.py`) with Phase 3's T003/T004 (see
  Parallel Opportunities note below).
- **User Story 3 (Phase 5)**: Depends on Foundational (T003, T011 for T021/T022) and on both
  Phase 3 (T006 for T023/T024) and Phase 4 (T012, T014 for T023/T024) — it documents both stories'
  output, so it cannot fully complete before both are done, though its citation-assertion tasks
  (T021, T022) can start as soon as their respective story's figure exists.
- **Polish (Phase 6)**: Depends on Phase 4's T014 (`predicted_death_age`) only — independent of
  Phase 3 and Phase 5's own completion, but pointless to demo before at least Phase 3 or 4 lands.

### Within Each Phase

- Foundational: T002 alone.
- User Story 1: T003 → T004 → T005 → T006 → T007, then T008/T009/T010 (parallel with each other).
- User Story 2: T011 → T012 → T013 (one chain); T014 → T015 and T014 → T016 (a second,
  independent chain — `models.py` vs. `loader.py`/`validation.py`); then T017/T018/T019 (parallel
  with each other), then T020.
- User Story 3: T021 depends on Phase 3; T022 depends on Phase 4; T023 depends on both stories;
  T024 depends on T023.
- Polish: T025 → T026; T027 → T028; T029 last (depends on everything).

### Parallel Opportunities

- Within User Story 1: T008, T009, and T010 in parallel once T004/T006 land.
- Within User Story 2: T014's chain (`scenario/`) and T011's chain (`mechanics/`) proceed
  independently of each other; T017/T018/T019 in parallel with each other once their respective
  chains land.
- **File-contention note**: T003/T004 (User Story 1) and T011/T012 (User Story 2) all edit
  `mechanics/social_security_benefit.py`. The two stories are otherwise fully independent and *can*
  be staffed in parallel, but these four tasks specifically should be sequenced (or their edits
  merged carefully) rather than attempted concurrently against the same file — unlike 016, where
  every foundational task lived in a genuinely shared, single-owner chain, this feature's two
  stories only share a file, not a dependency.
- Within Polish: T025 and T027 in parallel (different files); T026 follows T025, T028 follows T027.

---

## Parallel Example: User Story 1

```bash
Task: "Unit tests for compute_spousal_benefit_floor() in tests/unit/mechanics/test_social_security_benefit.py (T008)"
Task: "Integration tests for the spousal floor in tests/unit/comparison/test_projection.py (T009)"
Task: "Monte Carlo consistency test in tests/unit/simulation/test_monte_carlo.py (T010)"
```

## Parallel Example: User Story 2

```bash
# Two independent chains within this story:
Task: "Add compute_survivor_benefit() to mechanics/social_security_benefit.py (T011-T013)"
Task: "Add predicted_death_age to scenario/models.py, loader.py, validation.py (T014-T016)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational) — the shared result-type scaffolding.
2. Complete Phase 3 (User Story 1) — the spousal floor is live in every projection.
3. **STOP and VALIDATE**: run `pytest tests/unit/mechanics/test_social_security_benefit.py
   tests/unit/comparison/test_projection.py tests/unit/simulation/test_monte_carlo.py` and confirm
   green. This alone closes the larger of rp-52n's two gaps (SC-001, SC-002) with zero
   mortality/timeline concept needed.

### Incremental Delivery

1. Setup + Foundational → shared result types ready.
2. User Story 1 → the spousal floor ships and takes effect everywhere immediately — this is the
   deliverable with live projection impact.
3. User Story 2 → the survivor-benefit calculation and data-model field exist, cited and tested,
   ready for `rp-g8y` to consume — ships with zero behavior change to any existing projection.
4. User Story 3 → documentation/auditability catches up to the code (`docs/BRD.md`, citation
   checks) for both stories.
5. Polish → BFF/Streamlit plumbing for `predicted_death_age` so a scenario can set it outside
   direct YAML/Python use, plus the full four-suite quality gate.

### Notes

- Confirmed (research.md Decision 5) that **zero existing test fixtures need numeric correction**
  for User Story 1 — every MFJ fixture in this repo already uses a PIA pair comfortably above the
  spousal floor's 50% threshold. T009 is purely additive test coverage, not a fixture migration.
- User Story 2 is additive by construction (FR-006, FR-007) — no existing test should need any
  change at all because of it; T020 exists specifically to prove that, not merely assert it.
- T010 mirrors 016's own precedent (its `test_monte_carlo.py` consistency check) of adding an
  explicit regression guard for a shared call site even after confirming by import trace that the
  fix necessarily applies everywhere — belt-and-suspenders, not because the underlying reasoning is
  in doubt (`/speckit-analyze` finding C1).
- Per this repo's Conservative git profile (CLAUDE.md): no task here commits, pushes, or opens a
  PR — that remains a separate, explicitly-requested step after implementation.
