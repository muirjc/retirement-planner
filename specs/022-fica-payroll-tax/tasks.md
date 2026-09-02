---

description: "Task list for 022-fica-payroll-tax"
---

# Tasks: FICA Payroll Tax on Earned-Income Streams

**Input**: Design documents from `/specs/022-fica-payroll-tax/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — constitution's "Unit test coverage for numeric primitives" gate requires unit tests against reference values for `compute_fica_tax()` before it's used in any comparative run.

**Organization**: As with `021`, Phase 2 (Foundational) carries the actual `tax/fica.py` computation, since all three user stories exercise the same `compute_fica_tax()` with different input magnitudes (under wage base, over wage base, over Additional Medicare Tax threshold) rather than needing separate implementations.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Confirm `pytest tests/` passes on `022-fica-payroll-tax` before any change (baseline for SC-003)

---

## Phase 2: Foundational (blocks every user story)

- [x] T002 [P] Add `FicaTaxResult` dataclass to `src/retirement_planner/tax/models.py` (data-model.md § FicaTaxResult)
- [x] T003 [US-shared] Create `src/retirement_planner/tax/fica.py`: `OASDI_RATE`, `OASDI_WAGE_BASE` ($184,500, 2026, held flat), `MEDICARE_RATE`, `ADDITIONAL_MEDICARE_TAX_RATE` SourcedFigures + `ADDITIONAL_MEDICARE_TAX_THRESHOLDS: dict[FilingStatus, SourcedFigure[float]]` ($200k single / $250k MFJ) + `compute_fica_tax()` (contracts/tax-api.md) — depends on T002
- [x] T004 [US-shared] Export `compute_fica_tax`, `FicaTaxResult`, `OASDI_RATE`, `OASDI_WAGE_BASE`, `MEDICARE_RATE`, `ADDITIONAL_MEDICARE_TAX_RATE`, `ADDITIONAL_MEDICARE_TAX_THRESHOLDS` from `src/retirement_planner/tax/__init__.py` — depends on T003
- [x] T005 [P] [US-shared] Unit tests for `compute_fica_tax()` in `tests/unit/tax/test_fica.py`: under wage base (US1), over wage base — OASDI caps, Medicare doesn't (US2), over Additional Medicare Tax threshold for single and MFJ including the "combined MFJ triggers it, neither spouse alone does" case (US3), zero earned income for every member, `figures_used` always carries all five figures even at `$0`, `UnsupportedTaxYearError` for an undocumented year — depends on T003

**Checkpoint**: `compute_fica_tax()` fully correct in isolation. No projection wiring yet.

---

## Phase 3: User Story 1 - See the true cost of phased-retirement work (Priority: P1) 🎯 MVP

**Goal**: A configured `earned_income` stream's FICA cost is computed and actually funded from account balances each active year; `pension`/`annuity` streams are never subject to it.

**Independent Test**: quickstart.md §2-3 — a household with one `earned_income` stream shows FICA-funded balance reduction; a no-earned-income household is byte-for-byte unchanged.

### Implementation for User Story 1

- [x] T006 [US1] Add `_member_earned_income_amounts()` to `src/retirement_planner/comparison/projection.py`: filters each member's `income_streams` to `stream_type == "earned_income"`, sums `compute_income_stream_amount()` results (contracts/comparison-api.md) — depends on Phase 2
- [x] T007 [US1] Add `fica_tax: FicaTaxResult` (required) to `PlanYearProjection` in `src/retirement_planner/comparison/models.py`
- [x] T008 [US1] Add `cumulative_fica_tax_paid: float` to `PlanOutcome` in `src/retirement_planner/comparison/models.py`
- [x] T009 [US1] Wire `_member_earned_income_amounts()` + `compute_fica_tax()` into `run_plan_projection()`'s per-year loop: call after `compute_early_withdrawal_penalty()`, add `fica_tax.total_fica_tax` into `tax_owed`, union `fica_tax.figures_used` into the year's `figures_used`, set `fica_tax` on the constructed `PlanYearProjection` — depends on T006, T007
- [x] T010 [US1] Add `cumulative_fica_tax_paid = sum(year.fica_tax.total_fica_tax for year in years)` to `_derive_outcome()` — depends on T008, T009
- [x] T011 [P] [US1] Unit tests in `tests/unit/comparison/test_projection.py`: an `earned_income` stream's FICA is funded from account balances (ending balance lower than a no-FICA comparison), a `pension`/`annuity`-only household has `fica_tax.total_fica_tax == 0.0` every year, `cumulative_fica_tax_paid` sums correctly across years — depends on T009, T010
- [x] T012 [US1] Regression test: an existing no-`earned_income` scenario (e.g. `021`'s own pension-only fixtures) produces identical `PlanProjection` output except the new `fica_tax`/`cumulative_fica_tax_paid` fields (both zero) (SC-003) — depends on T009, T010

**Checkpoint**: User Story 1 fully functional — this is the MVP; rp-elp's core ask is met once this phase and Phase 4 are done.

---

## Phase 4: User Story 2 - See the Social Security wage base cap apply (Priority: P2)

**Goal**: OASDI caps at the wage base per member; Medicare doesn't.

**Independent Test**: quickstart.md §2 US2 — an `earned_income` stream above $184,500 shows a capped OASDI amount and an uncapped Medicare amount in the running projection.

- [x] T013 [US2] Integration test in `tests/unit/comparison/test_projection.py`: a member with earned income above the wage base shows `fica_tax.member_oasdi_tax[name] == OASDI_WAGE_BASE * OASDI_RATE` while `fica_tax.member_medicare_tax[name]` scales with the full amount — depends on Phase 3 (T009)

**Checkpoint**: Wage-base capping covered end-to-end (already correct at the `compute_fica_tax()` level from T005; this phase confirms it survives the projection wiring).

---

## Phase 5: User Story 3 - See the Additional Medicare Tax apply at high household earnings (Priority: P3)

**Goal**: Additional Medicare Tax applies once per household against combined earned income, including the two-spouses-each-under-threshold-but-combined-over case.

**Independent Test**: quickstart.md §2 US3 — a married household where each spouse individually earns under $200k but combined exceeds $250k shows nonzero `additional_medicare_tax`.

- [x] T014 [US3] Integration test in `tests/unit/comparison/test_projection.py`: MFJ household, two members each with an `earned_income` stream, neither individually over $200k but combined over $250k — `fica_tax.additional_medicare_tax > 0`, computed once (not doubled) — depends on Phase 3 (T009)
- [x] T015 [P] [US3] Integration test: a mid-horizon survivor-scenario filing-status switch (`018`) changes which Additional Medicare Tax threshold applies from the switch year forward — depends on Phase 3 (T009)

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T016 [P] Add `median_lifetime_fica_tax_paid: float` to `SummaryStatistics` in `src/retirement_planner/reporting/models.py` (contracts/reporting-api.md)
- [x] T017 Add `median_lifetime_fica_tax_paid` derivation to `summarize_run()` (Monte Carlo) and `_summarize_plan_projection()` (deterministic) in `src/retirement_planner/reporting/aggregation.py` — depends on T016, Phase 3
- [x] T018 [P] Unit tests for the new `SummaryStatistics` field in `tests/unit/reporting/test_aggregation.py` (both the Monte Carlo median and the deterministic single-value case) — depends on T017
- [x] T019 Add a "Lifetime FICA payroll tax paid" entry to `apps/streamlit_ui/src/rp_ui/narration.py`, immediately after the existing "Lifetime early-withdrawal penalty paid" entry (contracts/reporting-api.md) — depends on T017
- [x] T020 [P] Unit test for the new narration entry in `apps/streamlit_ui/tests/unit/test_narration.py` — depends on T019
- [x] T021 Update `docs/BRD.md`: new subsection describing FICA on `earned_income` streams (rates, wage base, Additional Medicare Tax, the W-2-only/no-SECA simplification), figure-verification table rows for the five new figures, and update the existing FICA/SECA "not modeled" note (§5.3, added by `021`) to reflect what's now modeled vs. what remains a gap (SECA specifically) — depends on Phase 3
- [x] T022 [P] Check `docs/SOLUTION_ARCHITECTURE.md` for whether the `tax` subpackage's component description needs a one-line mention (no new package/route — likely small, confirm) — depends on Phase 2
- [x] T023 [P] Check `README.md` for whether test counts need updating — depends on Phases 2-6
- [x] T024 Run full quickstart.md validation end-to-end
- [x] T025 Run all test suites (`pytest tests/`, `pytest apps/streamlit_ui/tests/`; BFF/e2e unaffected — confirm via a quick `pytest services/bff/tests/` pass since response shape is generic) and confirm green
- [x] T026 `bd close rp-elp` with a summary; confirm no further follow-on needed beyond the already-documented SECA gap (no new issue required — it's already named in `021`'s own BRD note, now more precisely scoped)

---

## Dependencies & Execution Order

- **Setup (T001)**: no dependencies.
- **Foundational (T002-T005)**: blocks every user story — `compute_fica_tax()` itself.
- **User Story 1 (T006-T012)**: depends on Foundational; the MVP, does the actual projection-loop wiring every later story's tests exercise.
- **User Story 2 (T013)**: depends on T009 — test only, wage-base capping is already correct from T003/T005.
- **User Story 3 (T014-T015)**: depends on T009 — tests only.
- **Polish (T016-T026)**: reporting/UI/docs — can start once Phase 3 lands.

## Implementation Strategy

### MVP First

Phases 1-3 (through T012) deliver rp-elp's core ask: `earned_income` streams' true after-tax cost, funded from cash flow. Phases 4-5 are test-only confirmations of behavior already correct from Phase 2's `compute_fica_tax()`. Phase 6 completes the reporting/UI/docs vertical `020`/`021` both established as this project's norm for a new tax figure.
