---

description: "Task list for 016-ss-claiming-age-actuarial-adjustment"
---

# Tasks: Social Security Claiming-Age Actuarial Adjustment

**Input**: Design documents from `/specs/016-ss-claiming-age-actuarial-adjustment/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The constitution's "Unit test coverage for numeric primitives" gate
(Development Workflow & Quality Gates) requires the new figure-driven calculation to have unit
tests against hand-calculated reference values before it's used in any comparative run.

**Organization**: Tasks are grouped by user story (spec.md) to enable independent implementation
and testing of each story.

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

**Purpose**: The cited calculation primitive every user story depends on. No user story task
below can be meaningfully implemented or tested until this phase is done.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `SocialSecurityBenefitResult` dataclass (`annual_benefit: float`, `adjustment_factor: float`, `figures_used: list[FigureUsage]`) to `src/retirement_planner/mechanics/models.py`, per data-model.md and contracts/mechanics-api.md
- [X] T003 Create `src/retirement_planner/mechanics/social_security_benefit.py`: private `_ClaimingAgeAdjustmentRates` dataclass, `SS_CLAIMING_AGE_ADJUSTMENT: SourcedFigure[_ClaimingAgeAdjustmentRates]` (5/9 of 1%/month first 36 months early, 5/12 of 1%/month beyond, 2/3 of 1%/month delayed capped at age 70; citation 42 U.S.C. §402(q)/(w), 20 C.F.R. §404.410/§404.313; cross-check the regulation text before setting `verified=True`, per the constitution's verified-figure gate), and `compute_social_security_benefit(primary_insurance_amount, full_retirement_age, claiming_age, tax_year) -> SocialSecurityBenefitResult` implementing the tiered early-reduction/delayed-credit formula from data-model.md (depends on T002)
- [X] T004 Re-export `compute_social_security_benefit` and `SocialSecurityBenefitResult` from `src/retirement_planner/mechanics/__init__.py` (depends on T003)
- [X] T005 [P] Unit tests for the formula in `tests/unit/mechanics/test_social_security_benefit.py`: claiming exactly at FRA (0% adjustment), the two textbook reference points (62 vs. 67 FRA → ~70% of PIA; 70 vs. 67 FRA → ~124% of PIA, SC-003), the 36-month tier-1/tier-2 boundary (spec.md Edge Cases), the age-70 delayed-credit cutoff, and `UnsupportedTaxYearError` for an undocumented tax year (depends on T003)
- [X] T006 [P] Add `full_retirement_age: float | None = None` to `HouseholdMember` in `src/retirement_planner/scenario/models.py`, with a docstring noting `ss_annual_benefit`'s meaning change to PIA and `full_retirement_age`'s default-to-claiming-age semantics (research.md Decision 3)
- [X] T007 Resolve `full_retirement_age`'s default (to that member's own `ss_claim_age`, cast to `float`) in `_build_household_member()` in `src/retirement_planner/scenario/loader.py`, mirroring the existing `hdhp_coverage` optional-field pattern (depends on T006)
- [X] T008 [P] Unit tests for the default-resolution behavior in `tests/unit/scenario/test_loader.py`: YAML omitting `full_retirement_age` resolves to `ss_claim_age`; YAML providing a distinct value round-trips unchanged (depends on T007)
- [X] T009 [P] Add the FRA-plausibility warning rule (`[65.0, 67.0]`, `severity="warning"`) to `_validate_household()` in `src/retirement_planner/scenario/validation.py`, per data-model.md (depends on T006)
- [X] T010 [P] Unit tests for the new validation rule in `tests/unit/scenario/test_validation.py`: FRA inside range → no flag; FRA outside range → one warning flag; existing `ss_claim_age` 62-70 blocking check still covered (depends on T009)

**Checkpoint**: `compute_social_security_benefit()` is implemented, cited, and unit-tested in
isolation; `HouseholdMember` carries and defaults `full_retirement_age` correctly. User story
implementation can now begin.

---

## Phase 3: User Story 1 - Claiming-age grid reflects the real trade-off (Priority: P1) 🎯 MVP

**Goal**: The 62-70 claiming-age comparison grid shows a genuinely different benefit amount per
candidate age, not a flat amount for a different number of years.

**Independent Test**: Run `compare_claiming_age_grid()` for a member with a known PIA and FRA
across ages 62, 67, 70 and confirm the benefit differs by the expected actuarial percentage at
each (quickstart.md §1).

### Implementation for User Story 1

- [X] T011 [US1] Change `_member_gross_social_security_benefits()` in `src/retirement_planner/comparison/projection.py` to return `tuple[dict[str, float], list[FigureUsage]]`: for each member who has reached their claiming age this plan year, call `compute_social_security_benefit()` with `primary_insurance_amount=member.ss_annual_benefit`, `full_retirement_age=member.full_retirement_age`, `claiming_age=claiming_ages[member.person_name]`, `tax_year=tax_year`, using `.annual_benefit` in place of the old flat `member.ss_annual_benefit` lookup; collect every result's `figures_used` (depends on T003, T004)
- [X] T012 [US1] Update `run_plan_projection()` in `src/retirement_planner/comparison/projection.py` to receive `_member_gross_social_security_benefits()`'s new `figures_used` return value and fold it into that plan year's existing `figures_used = [*mechanics_result.figures_used, *federal_tax.figures_used, ...]` list (depends on T011)
- [X] T013 [US1] Update both docstrings changed by T011/T012 (`_member_gross_social_security_benefits()`, `_household_gross_social_security_benefit()` if its own docstring still implies a flat amount) to describe the new claiming-age-adjusted behavior (depends on T011)

### Tests for User Story 1

- [X] T014 [P] [US1] Extend `tests/unit/comparison/test_compare_claiming_age_grid.py` with amount-varies-by-age cases matching spec.md Acceptance Scenarios 1-4: PIA differs correctly at 62/67/70; the 24-month (single-tier) and 60-month (both-tier) reduction cases; the 36-month delayed-credit cap (depends on T011, T012)
- [X] T015 [P] [US1] Add a regression case to `tests/unit/comparison/test_projection.py` (or wherever `_member_gross_social_security_benefits()` is already unit-tested) confirming a member whose `full_retirement_age` equals their `ss_claim_age` (the backward-compatible default) still receives exactly their configured `ss_annual_benefit`, unchanged from pre-feature behavior (depends on T011)

**Checkpoint**: User Story 1 fully functional and independently testable — SC-001, SC-003 satisfied.

---

## Phase 4: User Story 2 - Every projection uses the correct amount (Priority: P1)

**Goal**: A plain, non-comparison single-run projection and Monte Carlo simulation both use the
same claiming-age-adjusted benefit as the grid comparison — no path left on the old flat-amount
behavior.

**Independent Test**: Run a plain projection for a member claiming before FRA and confirm the
reduced amount is used in tax/cash-flow calculations; run a Monte Carlo simulation with the same
inputs and confirm it matches (quickstart.md §2).

**Note**: No new implementation task is needed here — T011/T012 (Phase 3) already fixed the one
shared call site every engine path funnels through (research.md Decision 4). This phase is
verification that the shared fix actually generalizes, per Principle II (Reproducibility).

### Tests for User Story 2

- [X] T016 [P] [US2] Add a plain (non-grid) single-run test in `tests/unit/comparison/test_projection.py`: a member claiming 3 years before a configured FRA receives the reduced amount in `PlanYearProjection.member_social_security_benefits` and in the income figures feeding federal/state tax (spec.md Acceptance Scenario 1) (depends on T011)
- [X] T017 [P] [US2] Add a Monte Carlo consistency test in `tests/unit/simulation/test_monte_carlo.py`: the same household/claiming-age inputs run through `run_simulation()` produce the identical adjusted benefit `run_plan_projection()` produces directly, for a fixed seed (spec.md Acceptance Scenario 2, Principle II) (depends on T011)

**Checkpoint**: User Stories 1 and 2 both independently verified — SC-002, SC-004 satisfied.

---

## Phase 5: User Story 3 - The adjustment rule is documented and auditable (Priority: P2)

**Goal**: The new figure carries the same citation/verification trail as every other regulated
figure in this codebase, and `docs/BRD.md` describes the new modeled behavior instead of implying
claiming age has no effect on benefit amount.

**Independent Test**: Inspect `SS_CLAIMING_AGE_ADJUSTMENT`'s `FigureUsage` output and confirm it
carries the statutory citation and a `last_verified` date; read `docs/BRD.md`'s Social Security
section and confirm it describes the adjustment (quickstart.md §3).

### Implementation for User Story 3

- [X] T018 [P] [US3] Add a citation-content assertion to `tests/unit/mechanics/test_social_security_benefit.py`: a computed `SocialSecurityBenefitResult.figures_used` entry named `ss_claiming_age_adjustment_rates` carries the expected citation text, a `last_verified` date, and `verified is True` (depends on T003, T005)
- [X] T019 [US3] Update `docs/BRD.md` §2.1's "Social Security claiming-age sensitivity" bullet to note the grid now varies benefit amount, not just timing; add a new subsection under §6.2 describing the PIA/FRA model and its citation, per data-model.md's "Modified: docs/BRD.md" section
- [X] T020 [US3] Run `specs/016-ss-claiming-age-actuarial-adjustment/quickstart.md`'s four snippets against the implemented code (interactively or as a scratch script) and confirm each prints the expected values (depends on T011, T012, T019)

**Checkpoint**: All three user stories independently functional — SC-005 satisfied.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mechanical ripple into the BFF and Streamlit UI packages (research.md Decision 6) —
not required for any single user story's own independent test, but required for a real user to
configure `full_retirement_age` through the API or UI rather than only via YAML or direct Python.

- [X] T021 [P] Add `full_retirement_age: float | None = None` to `HouseholdMemberRequest` in `services/bff/src/rp_bff/schemas.py`, mirroring `HouseholdMember` (contracts/scenario-api.md)
- [X] T022 [P] Extend `services/bff/tests/unit/test_resolution.py` and/or `services/bff/tests/integration/test_bff_lifecycle.py` with a case round-tripping `full_retirement_age` through the API, following that suite's existing per-field pattern (depends on T021)
- [X] T023 [P] Add a `full_retirement_age` input to `apps/streamlit_ui/pages/1_Scenarios.py` for both household member slots: session-state default, load-from-scenario assignment, `st.number_input` widget, and inclusion in the saved-scenario payload dict — mirroring the existing `ss_claim_age`/`ss_annual_benefit` pattern exactly (research.md Decision 6)
- [X] T024 [P] Extend `apps/streamlit_ui/tests/integration/test_app_pages.py` with coverage for the new field, following that suite's existing per-field pattern (depends on T023)
- [X] T025 [P] ~~Add an illustrative `full_retirement_age` value to `examples/reference_scenario.py` and to `config/scenarios/a.yaml`/`b.yaml`~~ -- **scope reduced during implementation**: `config/scenarios/a.yaml`/`b.yaml` turned out to be the repo owner's own real personal financial data (initials, real-looking dollar figures), not example fixtures -- left untouched rather than edited without being asked. `examples/reference_scenario.py` (a genuine generic library example) got an explicit `full_retirement_age=67.0` on both members instead, matching their existing `ss_claim_age` so the script's printed reference-case numbers are provably unchanged (verified by running it) while still making the new field visible in the flagship example.
- [X] T026 Run the full four-suite quality gate from CLAUDE.md/README.md: `pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`, `cd e2e && ../.venv/bin/python3.12 -m pytest -q` — confirm all green (depends on T001-T025)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS every user story phase.
- **User Story 1 (Phase 3)**: Depends on Foundational. The MVP — delivers the fix rp-n44 exists for.
- **User Story 2 (Phase 4)**: Depends on Foundational AND on Phase 3's T011/T012 (the shared call
  site) — this story is verification-only by design (research.md Decision 4), so it cannot start
  meaningfully before Phase 3's implementation tasks land, even though it has no new implementation
  of its own.
- **User Story 3 (Phase 5)**: Depends on Foundational (T003, T005 for T018) and on Phase 3
  (T011, T012 for T020's quickstart run). Independent of Phase 4.
- **Polish (Phase 6)**: Depends on Phase 2 (T006 for T021/T023) — independent of Phases 3-5's own
  completion but pointless to demo before at least Phase 3 lands.

### Within Each Phase

- Foundational: T002 → T003 → T004/T005; T006 → T007 → T008; T006 → T009 → T010. The three chains
  (`mechanics`, `loader`, `validation`) are mutually independent and parallelizable across chains.
- User Story 1: T011 → T012 → T013, then T014/T015 (parallel with each other).
- User Story 2: T016/T017 parallel with each other, both depend only on Phase 3's T011.
- User Story 3: T018 depends on Phase 2; T019 independent (docs-only); T020 depends on T011, T012, T019.
- Polish: T021 → T022; T023 → T024; T025 independent; T026 last (depends on everything).

### Parallel Opportunities

- Within Foundational: T002, T006 can start together; then the `mechanics` chain (T003→T005) and
  the `scenario` chain (T007→T010) proceed independently.
- Within User Story 1: T014 and T015 in parallel once T011/T012 land.
- User Story 2's T016 and T017 in parallel with each other; the whole phase can run alongside
  User Story 3 once Phase 3 is done.
- Within Polish: T021/T023/T025 in parallel (three different files); T022 follows T021, T024
  follows T023.

---

## Parallel Example: Foundational Phase

```bash
# Two independent chains can be staffed in parallel once T002/T006 land:
Task: "Create mechanics/social_security_benefit.py (T003)"
Task: "Resolve full_retirement_age default in scenario/loader.py (T007)"
Task: "Add FRA plausibility warning in scenario/validation.py (T009)"
```

## Parallel Example: User Story 1

```bash
Task: "Extend tests/unit/comparison/test_compare_claiming_age_grid.py (T014)"
Task: "Add backward-compatibility regression test in tests/unit/comparison/test_projection.py (T015)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational) — the cited calculation primitive and
   scenario-model changes.
2. Complete Phase 3 (User Story 1) — the claiming-age grid now shows real trade-offs.
3. **STOP and VALIDATE**: run `pytest tests/unit/mechanics/test_social_security_benefit.py
   tests/unit/comparison/test_compare_claiming_age_grid.py tests/unit/scenario/` and confirm green.
   This alone closes rp-n44's core defect (SC-001, SC-003).

### Incremental Delivery

1. Setup + Foundational → primitive ready, fully unit-tested in isolation.
2. User Story 1 → the headline grid feature fixed → this is the deliverable rp-n44 asked for.
3. User Story 2 → confirms no other engine path regressed or was left behind.
4. User Story 3 → documentation/auditability catches up to the code (BRD.md, citation checks).
5. Polish → BFF/Streamlit/e2e/example-scenario plumbing so the fix is reachable outside direct
   Python/YAML use, plus the full four-suite quality gate.

### Notes

- No task in this list requires a fixture-breaking migration (research.md Decision 3) — the ~34
  files a repo-wide grep found referencing `ss_annual_benefit` need no edits for correctness; T025
  is the only task that *chooses* to add new FRA values to existing example/config files, purely
  for illustrative value.
- Per this repo's Conservative git profile (CLAUDE.md): no task here commits, pushes, or opens a
  PR — that remains a separate, explicitly-requested step after implementation.
