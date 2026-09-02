---

description: "Task list for 021-pension-annuity-income"
---

# Tasks: Pension, Annuity & Phased-Retirement Income Streams

**Input**: Design documents from `/specs/021-pension-annuity-income/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — constitution's "Unit test coverage for numeric primitives" gate requires unit tests against reference values for a new numeric primitive (`compute_income_stream_amount()`) before it's used in any comparative run.

**Organization**: Phase 2 (Foundational) carries the actual data-model/computation work, since all three user stories exercise the *same* mechanism (`IncomeStream` + `compute_income_stream_amount()`) with different configurations (lifetime vs. windowed vs. earned-income) rather than needing separate implementations. Each user-story phase is therefore mostly the integration test proving that specific usage pattern, plus any story-specific wiring.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Confirm `pytest tests/` passes on `021-pension-annuity-income` before any change (baseline for SC-003's "byte-for-byte identical" regression check)

---

## Phase 2: Foundational (blocks every user story)

**Purpose**: The shared `IncomeStream` data model, scenario round-trip, validation, and the `compute_income_stream_amount()` numeric primitive every user story configures differently.

- [x] T002 [P] Add `IncomeStream` dataclass to `src/retirement_planner/scenario/models.py` (data-model.md § IncomeStream) and `HouseholdMember.income_streams: list[IncomeStream] = field(default_factory=list)`
- [x] T003 [P] Export `IncomeStream` from `src/retirement_planner/scenario/__init__.py` (mirror existing exports)
- [x] T004 [US-shared] Add `_build_income_stream()` to `src/retirement_planner/scenario/loader.py`, wired into `_build_household_member()` (contracts/scenario-api.md) — depends on T002
- [x] T005 [US-shared] Add `_income_stream_to_dict()` to `src/retirement_planner/scenario/store.py`, wired into `_scenario_to_dict()`'s per-member dict (contracts/scenario-api.md) — depends on T002
- [x] T006 [US-shared] Add income-stream validation rules (`end_age < start_age`, `annual_amount < 0`, both blocking) to `_validate_household()` in `src/retirement_planner/scenario/validation.py` (data-model.md § Validation) — depends on T002
- [x] T007 [P] [US-shared] Unit tests for `IncomeStream` parsing/defaulting in `tests/unit/scenario/test_loader.py` (present, absent-optional-fields, `ScenarioParseError` on missing required field) — depends on T004
- [x] T008 [P] [US-shared] Unit tests for `IncomeStream` save/load round-trip in `tests/unit/scenario/test_store.py` — depends on T005
- [x] T009 [P] [US-shared] Unit tests for the two new validation rules in `tests/unit/scenario/test_validation.py` — depends on T006
- [x] T010 [US-shared] Create `src/retirement_planner/mechanics/income_streams.py`: `INFLATION_RATE: SourcedFigure[float]` (2.40%, SSA 2025 Trustees Report intermediate assumption, `verified=True`, `last_verified=date(2026, 9, 2)`, research.md §1) and `compute_income_stream_amount(stream, member_age_this_year, tax_year, reference_tax_year) -> IncomeStreamAmountResult` (contracts/mechanics-api.md) — depends on T002
- [x] T011 [P] [US-shared] Add `IncomeStreamAmountResult` dataclass (`amount: float`, `figures_used: list[FigureUsage]`) to `src/retirement_planner/mechanics/models.py`
- [x] T012 [US-shared] Export `compute_income_stream_amount`, `IncomeStreamAmountResult`, `INFLATION_RATE` from `src/retirement_planner/mechanics/__init__.py` — depends on T010, T011
- [x] T013 [P] [US-shared] Unit tests for `compute_income_stream_amount()` in `tests/unit/mechanics/test_income_streams.py`: before/at/after `start_age`, at/after `end_age` (inclusive boundary), no `end_age` (lifetime), `cola_adjusted` flat across years, `fixed_nominal` erosion matches hand-calculated `annual_amount / (1+rate)**years` for a known year offset, `figures_used` empty for `cola_adjusted` and out-of-window, populated for active `fixed_nominal` — depends on T010

**Checkpoint**: `IncomeStream` fully parses, validates, round-trips, and computes a correct per-year amount in isolation. No projection wiring yet — nothing is visible in a running projection until Phase 3.

---

## Phase 3: User Story 1 - Model a lifetime pension (Priority: P1) 🎯 MVP

**Goal**: A configured pension (no `end_age`) appears as taxable ordinary income for every plan year at/after `start_age`, correctly flowing through tax, Roth-conversion bracket-fill, IRMAA/NIIT, and reporting.

**Independent Test**: quickstart.md §3-5 — configure one member with a lifetime pension, run `run_plan_projection()`, confirm `member_income_stream_amounts` and the resulting `ordinary_income`/tax figures are correct for years before and after `start_age`, and that a no-streams scenario is byte-for-byte unchanged.

### Implementation for User Story 1

- [x] T014 [US1] Add `income_stream_total: float = 0.0` and `income_stream_figures_used: list[FigureUsage] | None = None` params to `compute_plan_year_mechanics()` in `src/retirement_planner/mechanics/plan_year.py`, folded into `ordinary_income_established` before `compute_roth_conversion()` runs, and unioned into `figures_used` (contracts/mechanics-api.md) — depends on Phase 2
- [x] T015 [US1] Add `member_income_stream_amounts: dict[str, float] = field(default_factory=dict)` to `PlanYearProjection` in `src/retirement_planner/comparison/models.py` (contracts/comparison-api.md)
- [x] T016 [US1] Add `_member_income_stream_amounts(household, ages_this_year, tax_year, reference_tax_year)` to `src/retirement_planner/comparison/projection.py`, mirroring `_member_gross_social_security_benefits()` — depends on T010
- [x] T017 [US1] Wire `_member_income_stream_amounts()`'s output into `run_plan_projection()`'s per-year loop in `src/retirement_planner/comparison/projection.py`: pass `income_stream_total`/`income_stream_figures_used` into the `compute_plan_year_mechanics()` call, set `member_income_stream_amounts` on the constructed `PlanYearProjection` — depends on T014, T015, T016
- [x] T018 [P] [US1] Add `member_income_stream_amounts: dict[str, float] = field(default_factory=dict)` to `PlanYearAccountDetail` in `src/retirement_planner/reporting/account_attribution.py`, populated alongside `member_social_security_benefits` in `attribute_plan_projection()` (contracts/reporting-api.md)
- [x] T019 [P] [US1] Unit tests for the two new `compute_plan_year_mechanics()` parameters in `tests/unit/mechanics/test_plan_year.py`: `income_stream_total` reduces Roth-conversion bracket headroom the same way a traditional draw does, defaults reproduce prior output exactly — depends on T014
- [x] T020 [US1] Integration tests in `tests/unit/comparison/test_projection.py`: a lifetime `cola_adjusted` pension appears at full flat amount every year from `start_age` on, contributes to `ordinary_income`/federal & state tax/IRMAA MAGI, `member_income_stream_amounts` keyed correctly for a two-member household where only one has a pension — depends on T017
- [x] T021 [US1] Regression test in `tests/unit/comparison/test_projection.py` (or reuse an existing fixture): a scenario with zero configured `income_streams` produces an identical `PlanProjection` to its pre-feature output (SC-003) — depends on T017
- [x] T022 [P] [US1] Simulation-level check in `tests/unit/simulation/` (or extend an existing Monte Carlo test): a household with a pension produces a different (and internally consistent) success rate than the same household without one, confirming `run_plan_projection()`'s income-stream wiring reaches Monte Carlo paths with no separate change (FR-011/SC-004) — depends on T017

**Checkpoint**: User Story 1 fully functional — a lifetime pension/annuity is usable end-to-end. This is the MVP; `bd close rp-pid`'s "at minimum pensions and annuities" bar is met once this phase and Phase 4 are done.

---

## Phase 4: User Story 2 - Model a term-certain annuity (Priority: P2)

**Goal**: A stream with both `start_age` and `end_age` pays only inside that window; independent per-member windows on the same household don't interfere.

**Independent Test**: quickstart.md-style projection spanning years before, during, and after the window, for a household where two members each have their own independently-windowed annuity.

- [x] T023 [US2] Integration tests in `tests/unit/comparison/test_projection.py`: a windowed annuity contributes `0.0` before `start_age`, its full amount during `[start_age, end_age]` inclusive, and `0.0` after `end_age`; two members' independently-windowed streams don't cross-contaminate each other's `member_income_stream_amounts` entry — depends on Phase 3 (T017)
- [x] T024 [P] [US2] Edge-case unit tests in `tests/unit/mechanics/test_income_streams.py`: `end_age == start_age` (single-year window), overlapping streams on the same member summed correctly — depends on T010 (extends T013's file)

**Checkpoint**: Term-certain annuities (the originating issue's other explicitly named "at minimum" case) are fully covered.

---

## Phase 5: User Story 3 - Model phased-retirement earned income (Priority: P3)

**Goal**: An `earned_income` stream behaves identically to a pension/annuity for tax purposes (ordinary income, no FICA modeled), ending before a member's later Social Security claiming age.

**Independent Test**: quickstart.md-style projection where an earned-income stream's window ends a few years before SS claiming age, confirming ordinary income appears during the window and stops after, without any payroll-tax figure appearing anywhere in `figures_used`.

- [x] T025 [US3] Integration test in `tests/unit/comparison/test_projection.py`: an `earned_income` stream is included in ordinary taxable income exactly like a `pension`/`annuity` stream of the same shape — same code path, `stream_type` is purely informational (data-model.md) — depends on Phase 3 (T017)
- [x] T026 [P] [US3] Explicit non-regression assertion (in the same test or a dedicated one) that no FICA/payroll-tax figure or field appears anywhere in the result for an `earned_income` stream — guards the documented scope boundary (spec.md Assumptions) against silent scope creep later

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T027 [P] Add `IncomeStreamRequest` to `services/bff/src/rp_bff/schemas.py` and `income_streams: list[IncomeStreamRequest] = []` on `HouseholdMemberRequest` (contracts/scenario-api.md) — depends on T002
- [x] T028 [BFF] Round-trip test in `services/bff/tests/unit/test_resolution.py` (or `services/bff/tests/integration/test_bff_lifecycle.py`): `PUT /scenarios/{name}` with `income_streams` configured, then `GET` returns them unchanged — depends on T027
- [x] T029 Non-lossy pass-through in `apps/streamlit_ui/pages/1_Scenarios.py`: `_apply_scenario_to_form()` stashes each member's `income_streams` list into `session_state` unchanged; `_build_body()` resubmits it unchanged; no new editing widgets this iteration (plan.md Scope Boundaries) — depends on T027
- [x] T030 [P] Add a short `st.caption`/info note near each member's section in `1_Scenarios.py` noting that configured income streams are preserved on save but not yet editable here (points to editing the scenario file or the API) — depends on T029
- [x] T031 UI round-trip test in `apps/streamlit_ui/tests/integration/test_app_pages.py`: load a scenario with `income_streams` configured, save without touching any income-stream field, confirm they're still present afterward (no silent data loss) — depends on T029
- [x] T032 Update `docs/BRD.md`: new subsection under §6 (e.g. "6.x Pension, annuity & phased-retirement income streams") describing the model, the `cola_adjusted`/`fixed_nominal` treatment in this engine's real-dollar convention, and an explicit "not modeled: FICA/SECA on earned income" note — depends on Phase 3
- [x] T033 [P] Add the new `INFLATION_RATE` figure as a row in `docs/BRD.md`'s figure-verification table (§ figure table near the Social Security rows), with its citation and `verified=True`/last-verified date — depends on T010
- [x] T034 [P] Check `docs/SOLUTION_ARCHITECTURE.md` for whether any C4 diagram or dependency description needs a mention (no new package/route — likely a no-op, confirm and note if so) — depends on Phase 2
- [x] T035 [P] Check `README.md` for whether test counts need updating (new test files added) — depends on Phases 2-5
- [x] T036 Run full quickstart.md validation end-to-end
- [x] T037 Run all four test suites (`pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`, e2e if touched) and confirm green
- [x] T038 File follow-on `bd create` issues for explicitly out-of-scope work: (a) FICA/SECA modeling for `earned_income` streams, (b) full Streamlit UI editing widgets for income streams (plan.md Scope Boundaries) — depends on nothing, can run anytime

---

## Dependencies & Execution Order

- **Setup (T001)**: no dependencies.
- **Foundational (T002-T013)**: blocks every user story — this is where `IncomeStream`, its round-trip, validation, and `compute_income_stream_amount()` are actually built.
- **User Story 1 (T014-T022)**: depends on Foundational; this is the MVP and does the actual projection-loop wiring every later story reuses.
- **User Story 2 (T023-T024)**: depends on US1's wiring (T017) — adds no new production code, only tests, since windowing is already handled by `compute_income_stream_amount()` (T010).
- **User Story 3 (T025-T026)**: same — depends on T017, tests only.
- **Polish (T027-T038)**: BFF/UI/docs — T027 can start right after T002 (Foundational); T032-T035 want Phase 3 done so the described behavior is real.

## Parallel Example: Foundational phase

```text
Task: "Add IncomeStream dataclass to scenario/models.py"        (T002)
Task: "Export IncomeStream from scenario/__init__.py"           (T003, after T002)
Task: "Add IncomeStreamAmountResult to mechanics/models.py"      (T011, independent of T002's YAML plumbing)
```

## Implementation Strategy

### MVP First

Phases 1-3 (through T022) deliver the originating issue's full "at minimum pensions and annuities" bar for a lifetime pension. Phase 4 (term-certain annuity) is the second explicitly-named case and should ship in the same PR — it is nearly free once Phase 3 lands (windowing already exists in T010). Phase 5 (earned income) and Phase 6 (BFF/UI/docs) complete the full spec.

### Incremental Delivery

1. Phase 1 + 2 → foundation ready, nothing user-visible yet.
2. Phase 3 → lifetime pension usable end-to-end (core library). 
3. Phase 4 → term-certain annuities covered (tests only, near-zero marginal code).
4. Phase 5 → phased-retirement earned income covered (tests only).
5. Phase 6 → BFF/API parity, non-lossy UI round-trip, docs, follow-on issues filed.
