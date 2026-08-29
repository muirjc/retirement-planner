---

description: "Task list for Advanced Tax & Benefits Modeling"
---

# Tasks: Advanced Tax & Benefits Modeling (IRMAA, NIIT, HSA)

**Input**: Design documents from `/specs/010-advanced-tax-benefits/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/) (`tax-api.md`, `mechanics-api.md`, `comparison-api.md`, `scenario-api.md`), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's own Testing section requires unit tests for each new numeric primitive against hand-calculated reference values (the constitution's "Unit test coverage for numeric primitives" gate), plus integration tests through `run_plan_projection()`, matching every prior engine feature's (`002`/`003`/`005`) practice.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1–US3)
- File paths are exact and relative to the repository root

## Path Conventions

This feature extends the existing core library (`src/retirement_planner/`) — no new package, no new dependency. It also makes small, additive edits to `services/bff` (`007`). See [plan.md](./plan.md) Project Structure for the full file list.

**Story dependency shape, different from a typical independent-stories feature**: All three stories add their own new module (`irmaa.py`/`niit.py`/`hsa.py`) and their own new result type, but each also edits the *same* shared files — `comparison/projection.py` (the one integration point every story plugs into) and `comparison/models.py` (`PlanYearProjection`/`PlanOutcome`). Because of that shared-file overlap, the stories are sequenced **US1 → US2 → US3** (matching spec.md's own P1 > P2 > P3 priority order) rather than built in parallel — not because any story's *logic* depends on another's, but to avoid three simultaneous edits to the same handful of lines. Each story's own Acceptance Scenarios and Independent Test remain satisfiable without the others, per spec.md.

---

## Phase 1: Setup

**Purpose**: Confirm the existing package needs no new dependency before adding anything to it

- [X] T001 Confirm no new dependency is needed for this feature (plan.md's Technical Context — pure stdlib, same as every existing tax/mechanics module) — run `pytest tests/ services/bff/tests/` to confirm the existing 191 core + 43 bff tests pass as a pre-change baseline

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one piece of shared infrastructure both User Story 1 (IRMAA) and User Story 2 (NIIT) need before either can compute a threshold determination — a consistent MAGI approximation (research.md §2), computed once, not reimplemented per mechanism

**⚠️ CRITICAL**: User Stories 1 and 2 cannot begin until this phase is complete. User Story 3 (HSA) does not depend on this phase (HSA eligibility is age/coverage/enrollment-based, not income-based) but is still sequenced after US1/US2 per the shared-file note above.

- [X] T002 [P] Unit test the MAGI-approximation helper (`ordinary_income + taxable_social_security`, research.md §2) against hand-calculated cases in `tests/unit/comparison/test_projection.py` — write FIRST, ensure it FAILS before T003
- [X] T003 Implement `_approximate_magi()` as a private helper in `src/retirement_planner/comparison/projection.py` (depends on T002)

**Checkpoint**: Foundation ready — User Story 1 implementation can now begin

---

## Phase 3: User Story 1 - See the Medicare premium surcharge a strategy triggers (Priority: P1) 🎯 MVP

**Goal**: A user can see, for any plan year, whether a household's income crosses an IRMAA threshold and what surcharge results — distinct from ordinary income tax, per Medicare-enrolled member.

**Independent Test**: Run two otherwise-identical scenarios differing only in income on each side of a known threshold and confirm a materially different total cost for the one that crosses it — independent of NIIT or HSA modeling.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T007

- [X] T004 [P] [US1] Unit test `compute_irmaa_surcharge()` in `tests/unit/tax/test_irmaa.py` — MAGI below every tier → no surcharge; MAGI exactly at a tier's `magi_threshold` → that tier applies (inclusive lower bound, Edge Cases); MAGI crossing a tier → `surcharge_owed` equals `annual_surcharge_per_person * enrolled_member_count`; `enrolled_member_count=0` → no surcharge regardless of MAGI (FR-004); `UnsupportedTaxYearError` for an undocumented `tax_year`
- [X] T005 [US1] Integration test: a household whose Roth conversion crosses an IRMAA tier shows `PlanYearProjection.irmaa.surcharge_owed > 0` and `PlanOutcome.cumulative_irmaa_paid` reflecting it, distinct from `cumulative_tax_paid`; a household with no Medicare-eligible member shows no surcharge in any plan year (Acceptance Scenarios US1.1-US1.4) in `tests/integration/test_advanced_tax_benefits_lifecycle.py` (new file, mirroring `002`/`003`/`005`'s own one-integration-file-per-feature convention)

### Implementation for User Story 1

- [X] T006 [US1] Add `IrmaaTierRow`, `IrmaaTierTable`, `IrmaaResult` to `src/retirement_planner/tax/models.py` (contracts/tax-api.md) (depends on T004)
- [X] T007 [US1] Implement `src/retirement_planner/tax/irmaa.py` — illustrative `verified=False` IRMAA tier `SourcedFigure` schedule by filing status (citation naming CMS.gov's IRMAA tables, research.md §7) + `compute_irmaa_surcharge()` (depends on T004, T006)
- [X] T008 [US1] Export `compute_irmaa_surcharge`/`IrmaaResult`/`IrmaaTierRow`/`IrmaaTierTable` from `src/retirement_planner/tax/__init__.py` (depends on T007)
- [X] T009 [US1] Add `PlanYearProjection.irmaa: IrmaaResult` and `PlanOutcome.cumulative_irmaa_paid: float` to `src/retirement_planner/comparison/models.py` (depends on T007)
- [X] T010 [US1] Wire IRMAA into `run_plan_projection()` in `src/retirement_planner/comparison/projection.py` — call `_approximate_magi()`, determine `income_basis`/look-back MAGI from the loop's own accumulated `years` list (`years[-2]` when available, else `current_year_proxy`, research.md §3), determine `enrolled_member_count` from that year's `ages_this_year` (age >= 65), call `compute_irmaa_surcharge()`, populate `PlanYearProjection.irmaa`, update `_derive_outcome()` to sum `cumulative_irmaa_paid` (depends on T003, T009, T005)

**Checkpoint**: User Story 1 is independently functional — quickstart.md §1 passes end-to-end.

---

## Phase 4: User Story 2 - See the investment-income surtax a strategy triggers (Priority: P2)

**Goal**: A user can see, for any plan year, whether a household's investment income crosses the NIIT threshold and what surtax results.

**Independent Test**: Run a scenario with taxable-account investment income above and below the known threshold and confirm the surtax appears only when crossed — independent of IRMAA or HSA modeling.

### Tests for User Story 2 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T014

- [X] T011 [P] [US2] Unit test `compute_niit()` in `tests/unit/tax/test_niit.py` — MAGI at/below threshold → no surtax; MAGI above threshold → `surtax_owed` equals `rate * min(investment_income, magi - threshold)` (data-model.md's lesser-of rule), never against full `investment_income`; `UnsupportedTaxYearError` for an undocumented `tax_year`
- [X] T012 [US2] Integration test: a household whose taxable-account withdrawals push investment income above the NIIT threshold shows `PlanYearProjection.niit.surtax_owed > 0` and `PlanOutcome.cumulative_niit_paid` reflecting it; a Roth conversion that raises ordinary income without raising investment income does not itself trigger the surtax on its own (Acceptance Scenarios US2.1-US2.3) — appended to `tests/integration/test_advanced_tax_benefits_lifecycle.py`

### Implementation for User Story 2

- [X] T013 [US2] Add `NiitResult` to `src/retirement_planner/tax/models.py` (contracts/tax-api.md) (depends on T011)
- [X] T014 [US2] Implement `src/retirement_planner/tax/niit.py` — illustrative `verified=False` NIIT threshold (by filing status) and rate `SourcedFigure` schedules (citation naming IRC §1411) + `compute_niit()` (depends on T011, T013)
- [X] T015 [US2] Export `compute_niit`/`NiitResult` from `src/retirement_planner/tax/__init__.py` (depends on T014)
- [X] T016 [US2] Add `PlanYearProjection.niit: NiitResult` and `PlanOutcome.cumulative_niit_paid: float` to `src/retirement_planner/comparison/models.py` (depends on T014)
- [X] T017 [US2] Wire NIIT into `run_plan_projection()` in `src/retirement_planner/comparison/projection.py` — compute `investment_income` as that year's taxable-account withdrawal amount (`mechanics_result.withdrawal_plan.sequence_withdrawals` filtered to `account_type == "taxable"`, research.md §1), reuse `_approximate_magi()`, call `compute_niit()`, populate `PlanYearProjection.niit`, update `_derive_outcome()` to sum `cumulative_niit_paid` (depends on T003, T016, T012)

**Checkpoint**: User Stories 1 and 2 are both independently functional — quickstart.md §1–2 pass end-to-end.

---

## Phase 5: User Story 3 - Model HSA contribution eligibility as a real constraint (Priority: P3)

**Goal**: A user can see each household member's HSA contribution eligibility reflected correctly per plan year, including the 6-month Medicare backdating trap and the younger-spouse-retains-eligibility case.

**Independent Test**: Construct a household where one member enrolls in Medicare mid-scenario and confirm HSA eligibility for that member ends at the correct point, while an eligible younger spouse's contributions continue — independent of IRMAA/NIIT modeling.

### Tests for User Story 3 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T022

- [X] T018 [P] [US3] Unit test `compute_hsa_eligibility()` and `compute_hsa_contribution()` in `tests/unit/mechanics/test_hsa.py` — a member with `hdhp_coverage=True` and not Medicare-enrolled is eligible; a Medicare-enrolled member is never eligible regardless of coverage; one eligible member → self-only limit; two eligible members → family limit; an eligible member 55+ → catch-up added; no eligible member → `amount_contributed=0.0` with a `rejected_reason` (FR-012, research.md §5, never an exception); a configured amount above the applicable limit is capped, not silently exceeded; `UnsupportedTaxYearError` for an undocumented `tax_year`'s limit figure
- [X] T019 [US3] Integration test: a household with an older member enrolling in Medicare partway through the modeled horizon and a younger, `hdhp_coverage=True` spouse shows the younger spouse's contribution eligibility continuing unaffected after the older member's enrollment plan year, and shows `ordinary_income` reduced by the modeled contribution amount in every eligible year (Acceptance Scenarios US3.1-US3.4) — appended to `tests/integration/test_advanced_tax_benefits_lifecycle.py`

### Implementation for User Story 3

- [X] T020 [US3] Add `HouseholdMember.hdhp_coverage: bool = False`, `HsaContributionPlan`, and `Scenario.hsa_contribution: HsaContributionPlan | None = None` to `src/retirement_planner/scenario/models.py` (contracts/scenario-api.md) (depends on T018)
- [X] T021 [US3] Add `HsaEligibility`, `HsaContributionResult` to `src/retirement_planner/mechanics/models.py` (contracts/mechanics-api.md) (depends on T018)
- [X] T022 [US3] Implement `src/retirement_planner/mechanics/hsa.py` — illustrative `verified=False` HSA contribution-limit `SourcedFigure` schedule (self-only, family, 55+ catch-up; citation naming the IRS's annual Rev. Proc. HSA-limits announcement) + `compute_hsa_eligibility()` + `compute_hsa_contribution()` (depends on T018, T021)
- [X] T023 [US3] Export `compute_hsa_eligibility`/`compute_hsa_contribution`/`HsaEligibility`/`HsaContributionResult` from `src/retirement_planner/mechanics/__init__.py` (depends on T022)
- [X] T024 [US3] Add the optional `hsa_contribution: HsaContributionResult | None = None` parameter to `compute_plan_year_mechanics()` in `src/retirement_planner/mechanics/plan_year.py` — when provided, reduces the returned `ordinary_income` by `hsa_contribution.amount_contributed` and folds its `figures_used` into the union (contracts/mechanics-api.md) (depends on T022)
- [X] T025 [US3] Add `StrategyConfiguration.hsa_contribution: HsaContributionPlan | None = None` and `PlanYearProjection.hsa_contribution: HsaContributionResult` to `src/retirement_planner/comparison/models.py` (contracts/comparison-api.md's correction) (depends on T022)
- [X] T026 [US3] Wire HSA into `run_plan_projection()` in `src/retirement_planner/comparison/projection.py` — build per-member `(person_name, age, hdhp_coverage)` from that year's `ages_this_year`/`household`, determine `medicare_enrolled` per member (age >= 65), call `compute_hsa_eligibility()` then, when `strategy.hsa_contribution` is not `None`, `compute_hsa_contribution()`, pass the result into `compute_plan_year_mechanics()`, populate `PlanYearProjection.hsa_contribution` (depends on T003, T024, T025, T019)
- [X] T027 [US3] Add one line to each of `004`'s 3 `compare_*()` functions in `src/retirement_planner/comparison/compare.py`, forcing `hsa_contribution` onto every candidate before running, alongside each function's existing forced fields (contracts/comparison-api.md) (depends on T025)
- [X] T028 [US3] Add the same one line to each of `005`'s 4 `compare_*()` functions in `src/retirement_planner/simulation/compare.py` (depends on T025)
- [X] T029 [US3] Update `services/bff/src/rp_bff/schemas.py` — `HouseholdMemberRequest` gains `hdhp_coverage: bool = False`; a new `HsaContributionPlanRequest` mirrors `HsaContributionPlan`; `ScenarioRequest` gains `hsa_contribution: HsaContributionPlanRequest | None = None` (depends on T020)
- [X] T030 [US3] Update `resolve_run_context()` in `services/bff/src/rp_bff/resolution.py` to resolve `scenario.hsa_contribution` into the `StrategyConfiguration.hsa_contribution` it already builds there, mirroring how it already resolves `scenario.roth_conversion` into that object's conversion fields (depends on T025, T029)

**Checkpoint**: All three user stories are independently functional — quickstart.md §1–3 pass end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Surface the new figures through the existing reporting/export mechanism, verify the constitution's watch items empirically, and tie the quickstart walkthrough together as one acceptance run

- [X] T031 [P] Add `cumulative_irmaa_paid`/`cumulative_niit_paid` columns to `006`'s CSV export functions in `src/retirement_planner/reporting/export.py`, following the same column-per-`PlanOutcome`-field pattern already in place for `cumulative_tax_paid`, plus a unit test in `tests/unit/reporting/test_export.py` (depends on T009, T016)
- [X] T032 [P] Verify every new figure (`IrmaaTierTable`, NIIT threshold/rate, HSA contribution limits) defaults `verified=False` and its `FigureUsage` propagates into `PlanYearProjection.figures_used`/`unverified_figure_names` correctly — a dedicated auditability test in `tests/integration/test_advanced_tax_benefits_lifecycle.py`, mirroring the "needs verification" propagation check every prior tax-figure feature already has (Principle III) (depends on T010, T017, T026)
- [X] T033 Measure reference-scale performance (5,000 paths × 3 states, `005`'s own benchmark shape) before and after this feature's changes and confirm no material regression against the constitution's Performance Budget, per plan.md's own stated watch item — record the measured delta in this feature's own notes rather than asserting the budget holds without checking (depends on T010, T017, T026)
- [X] T034 Add docstrings to every new module (`irmaa.py`, `niit.py`, `hsa.py`) and every new/modified type, each referencing the corresponding contracts doc section (depends on T007, T014, T022)
- [X] T035 Run the complete [quickstart.md](./quickstart.md) walkthrough (all 3 sections) as one end-to-end assertion sequence in `tests/integration/test_advanced_tax_benefits_lifecycle.py` (depends on T005, T012, T019)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS User Stories 1 and 2 (not User Story 3, which needs no MAGI helper, but US3 is still sequenced after US1/US2 per the shared-file note)
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational; sequenced after User Story 1 only because both edit the same lines of `comparison/projection.py`/`comparison/models.py` — no logical dependency on US1's own IRMAA behavior
- **User Story 3 (Phase 5)**: Sequenced after User Story 2 for the same shared-file reason; no logical dependency on IRMAA or NIIT
- **Polish (Phase 6)**: `T031`/`T032`/`T033` depend on all three stories' wiring being complete (`T010`, `T017`, `T026`); `T034`/`T035` depend on every story's implementation

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Foundational only — the MVP slice
- **User Story 2 (P2)**: Depends on Foundational; shares files with US1 (sequenced, not logically dependent)
- **User Story 3 (P3)**: Shares files with US1/US2 (sequenced, not logically dependent); its own new files (`hsa.py`, `scenario/models.py`'s new fields) could in principle be built in parallel with US1/US2 by a second contributor, merging the shared-file edits (`comparison/models.py`, `comparison/projection.py`) last

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task
- New result types (`models.py` additions) before the compute module that returns them
- The compute module before its subpackage's `__init__.py` export
- The compute module and its export before wiring into `run_plan_projection()`

### Parallel Opportunities

- T002 (Foundational test) can proceed as soon as Setup (T001) confirms the baseline
- T004 (US1 unit test) and T011 (US2 unit test) target different, isolated new files (`test_irmaa.py`/`test_niit.py`) and could be authored in parallel by different contributors even though their implementation tasks are sequenced by the shared-file constraint
- T018 (US3 unit test) is similarly isolated (`test_hsa.py`)
- T031/T032 in Polish can run in parallel — different files, independent concerns

---

## Parallel Example: Test authoring across all three stories

```bash
# Once Foundational (T002-T003) is done, all three stories' own unit
# tests can be drafted in parallel (different, new, isolated files) even
# though their implementation tasks land sequentially due to the shared
# comparison/projection.py and comparison/models.py edits:
Task: "Unit test compute_irmaa_surcharge() in tests/unit/tax/test_irmaa.py"
Task: "Unit test compute_niit() in tests/unit/tax/test_niit.py"
Task: "Unit test compute_hsa_eligibility()/compute_hsa_contribution() in tests/unit/mechanics/test_hsa.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest tests/` and confirm SC-001 holds via quickstart.md §1
5. IRMAA alone already delivers the single largest currently-invisible cost spec.md's own "Why this priority" names — a defensible MVP on its own, before NIIT or HSA exist

### Incremental Delivery

1. Setup + Foundational → shared MAGI helper ready
2. Add User Story 1 → IRMAA surcharge visibility → validate independently (SC-001) → this is the MVP
3. Add User Story 2 → NIIT surtax visibility → validate independently (SC-002)
4. Add User Story 3 → HSA eligibility modeling, including the `004`/`005` `compare_*()` threading and the `007` BFF resolution → validate independently (SC-003)
5. Polish → CSV export columns, auditability propagation check, measured performance confirmation, full quickstart.md walkthrough (SC-004)

### Suggested Team Split

Given the shared-file sequencing constraint, a single contributor working US1 → US2 → US3 in order is the simplest path. If staffed with two contributors: one builds each story's own new, isolated files (the compute module + its unit test + its `__init__.py` export) while the other integrates each into `comparison/projection.py`/`comparison/models.py` once the isolated piece is ready — but the integration step itself must still happen in US1 → US2 → US3 order, since each edits the same lines the previous one just added.
