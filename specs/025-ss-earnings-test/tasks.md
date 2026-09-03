---

description: "Task list for 025-ss-earnings-test"
---

# Tasks: Social Security Earnings Test (Withholding + FRA Recredit)

**Input**: Design documents from `/specs/025-ss-earnings-test/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — constitution's "Unit test coverage for numeric primitives" gate requires unit
tests against reference (SSA-published) values for both new mechanics operations before either is
used in any comparative run.

**Organization**: Mirrors `022`'s own precedent — Phase 2 (Foundational) carries the actual
`compute_earnings_test_withholding()`/`compute_earnings_test_recredit()` math (all three user
stories exercise the same two functions with different inputs: regular-rate withholding for US1,
the recredit call for US2, the FRA-year rate/threshold for US3), and each user story's own phase is
the projection-loop wiring and integration tests specific to that story.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Confirm `pytest tests/` passes on `025-ss-earnings-test` before any change (baseline for SC-003)

---

## Phase 2: Foundational (blocks every user story)

- [X] T002 [P] Add `EarningsTestWithholdingResult` and `EarningsTestRecreditResult` dataclasses to `src/retirement_planner/mechanics/models.py` (data-model.md)
- [X] T003 [US-shared] In `src/retirement_planner/mechanics/social_security_benefit.py`: add `_EarningsTestRates` dataclass, `SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA` ($24,480/yr, 2026, held flat) and `SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR` ($65,160/yr, 2026, held flat) `SourcedFigure`s, citing the 2026 SSA COLA Fact Sheet (research.md Decision 2) — depends on T002
- [X] T004 [US-shared] Implement `compute_earnings_test_withholding()` in the same module (contracts/mechanics-api.md): applies FR-003 ($1-for-$2, below-FRA threshold) or FR-004 ($1-for-$3, FRA-year threshold) per `is_fra_attainment_year`, floors `benefit_after_withholding` at 0.0, computes `deduction_months_this_year = min(12, ceil(withheld_amount / (primary_insurance_amount / 12)))` (research.md Decision 4) — depends on T003
- [X] T005 [US-shared] Implement `compute_earnings_test_recredit()` in the same module (contracts/mechanics-api.md): converts `cumulative_months_withheld` into a permanently reduced "months early" figure for the early-claiming reduction formula already in `compute_social_security_benefit()`, capping `recredited_adjustment_factor` at 1.0 (research.md Decision 4) — depends on T003
- [X] T006 [US-shared] Export `compute_earnings_test_withholding`, `compute_earnings_test_recredit`, `EarningsTestWithholdingResult`, `EarningsTestRecreditResult`, `SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA`, `SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR` from `src/retirement_planner/mechanics/__init__.py` — depends on T004, T005
- [X] T007 [P] [US-shared] Unit tests for `compute_earnings_test_withholding()` in `tests/unit/mechanics/test_social_security_benefit.py`: below-FRA withholding matches SSA's $1-for-$2 formula against the 2026 exempt amount (US1), earnings at/below threshold withhold $0 (US1 edge case), FRA-year $1-for-$3 formula against the higher threshold (US3), withholding never drives `benefit_after_withholding` below 0.0 even for extreme earned income, `deduction_months_this_year` credits a full month for partial-month withholding, `UnsupportedTaxYearError` for an undocumented year — depends on T004
- [X] T008 [P] [US-shared] Unit tests for `compute_earnings_test_recredit()` in the same test file: `cumulative_months_withheld == 0` leaves the benefit unchanged (US2 edge case), a nonzero total permanently raises `recredited_adjustment_factor` toward 1.0, the recredit never exceeds 1.0 even when `cumulative_months_withheld` is large enough to fully cover the original early-claiming reduction — depends on T005

**Checkpoint**: Both new operations fully correct in isolation. No projection wiring yet.

---

## Phase 3: User Story 1 - See the near-term benefit actually withheld (Priority: P1) 🎯 MVP (part 1 of 2)

**Goal**: A member claiming before FRA with concurrent earned income above the exempt threshold
sees their projected Social Security benefit correctly reduced for every year withholding applies.

**Independent Test**: quickstart.md §1, §4 (withheld-year portion) — a member's near-term benefit is
measurably lower than the unwithheld claiming-age-adjusted amount; a member with no `earned_income`
overlap is unaffected.

### Implementation for User Story 1

- [X] T009 [US1] Add `member_ss_earnings_test_withheld: dict[str, float]` (default `{}`) to `PlanYearProjection` in `src/retirement_planner/comparison/models.py` (data-model.md)
- [X] T010 [US1] In `src/retirement_planner/comparison/projection.py`, move the existing `_member_earned_income_amounts()` call earlier in `run_plan_projection()`'s per-year loop (before `_member_gross_social_security_benefits()`) so both the earnings test and the existing FICA call site share one result instead of each recomputing it — depends on Phase 2
- [X] T011 [US1] Add a `cumulative_earnings_test_months_withheld: dict[str, int]` local variable (initialized `{}`, mirrors `roth_conversion_lots`'s own "purely local" precedent) at the top of `run_plan_projection()`, before its per-year `while` loop — depends on Phase 2
- [X] T012 [US1] Extend `_member_gross_social_security_benefits()`'s signature to accept `member_earned_income: dict[str, float]` and `full_retirement_age_by_member` context it can already derive via its existing `_resolved_full_retirement_age()` helper; for each member who has claimed and whose `ages_this_year[member] <= floor(full_retirement_age)`, call `compute_earnings_test_withholding()` with that member's own claiming-age-adjusted benefit and earned income, apply `benefit_after_withholding` in place of the raw benefit, and record `deduction_months_this_year` into a returned per-member dict — depends on T004, T010
- [X] T013 [US1] Thread the new per-member withheld-amount dict from T012 into `PlanYearProjection.member_ss_earnings_test_withheld` at its construction site in `run_plan_projection()`, and union the withholding call's `figures_used` into that year's existing `figures_used` list — depends on T009, T012
- [X] T014 [P] [US1] Unit tests in `tests/unit/comparison/test_projection.py`: a member claiming before FRA with earned income above the below-FRA threshold shows a reduced `member_social_security_benefits` entry and a nonzero `member_ss_earnings_test_withheld` entry for that year; a member with earned income at/below the threshold, or no `earned_income` stream at all, shows `member_ss_earnings_test_withheld == 0.0` every year — depends on T013
- [X] T015 [US1] Regression test: an existing scenario fixture with no member combining early claiming and concurrent `earned_income` (every scenario predating this feature) produces identical `PlanProjection` output except the new `member_ss_earnings_test_withheld` field (all `0.0`) (SC-003) — depends on T013

**Checkpoint**: Withholding is correctly computed and applied in a running projection. Benefit is
reduced but not yet recredited — Phase 4 completes the MVP.

---

## Phase 4: User Story 2 - See withheld benefits recredited at FRA, not simply lost (Priority: P1) 🎯 MVP (part 2 of 2)

**Goal**: A member's benefit permanently steps up at their FRA-attainment year, reflecting SSA's ARF
recredit of every prior year's withheld amount — closing the "withholding with no payback" gap the
issue's own acceptance criteria treats as equally wrong as modeling nothing.

**Independent Test**: quickstart.md §3-4 — a previously-withheld member's post-FRA benefit exceeds
their original claiming-age-adjusted amount; a never-withheld member sees no such step-up.

### Implementation for User Story 2

- [X] T016 [US2] In `_member_gross_social_security_benefits()` (or its caller in `run_plan_projection()`), for the specific plan year `ages_this_year[member] == floor(full_retirement_age)` (the member's FRA-attainment year), call `compute_earnings_test_recredit()` with that member's accumulated `cumulative_earnings_test_months_withheld[member]` total (from every prior plan year, T012) and apply `recredited_annual_benefit` as that member's benefit from this year forward — depends on T005, T011, T012
- [X] T017 [US2] Ensure the recredited benefit, once applied, persists for every subsequent plan year (the member's `full_retirement_age`-vs-`claiming_age` reduction is now permanently smaller) without re-deriving the original unwithheld reduction each year — depends on T016
- [X] T018 [P] [US2] Unit tests in `tests/unit/comparison/test_projection.py`: a member withheld in one or more pre-FRA years shows a permanently higher `member_social_security_benefits` entry from their FRA-attainment year forward than their original claiming-age-adjusted amount, and that higher amount persists through every later plan year; a member who claimed before FRA but was never withheld shows no change at their FRA year (SC-002) — depends on T017
- [X] T019 [US2] Regression test: re-run the SC-003 fixture from T015 to confirm the recredit call, now wired, still leaves a no-withholding scenario byte-for-byte unchanged (recredit of a zero cumulative total is a no-op) — depends on T017

**Checkpoint**: Both P1 user stories complete — rp-acq's core ask (withholding + recredit, not one
without the other) is met.

---

## Phase 5: User Story 3 - See the more lenient rule apply in the FRA-attainment year (Priority: P2)

**Goal**: The FRA-attainment year itself uses the higher exempt amount and $1-for-$3 ratio, not the
stricter before-FRA rule.

**Independent Test**: quickstart.md §2 — a member reaching FRA during the current plan year, with
earned income between the two years' thresholds, is withheld at the FRA-year rate.

- [X] T020 [US3] Integration test in `tests/unit/comparison/test_projection.py`: a member whose `ages_this_year[member] == floor(full_retirement_age)` this plan year, with earned income above the FRA-year exempt amount but below what the stricter below-FRA threshold would allow, shows withholding computed at the FRA-year rate (confirms `is_fra_attainment_year=True` is passed correctly at T012's call site) — depends on Phase 3 (T012)

**Checkpoint**: All three user stories independently functional (FRA-year rate selection was already
correct at the `compute_earnings_test_withholding()` level from T007; this phase confirms it
survives the projection wiring, mirroring `022`'s own Phase 4/5 pattern).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T021 Update `docs/BRD.md` §6.2a: replace the "explicitly not modeled" earnings-test sentence with a description of what's now modeled (withholding + FRA recredit), naming the whole-plan-year simplifications (research.md Decisions 3-4) explicitly, not silently absorbed
- [X] T022 Update `docs/BRD.md` §5.3: remove or narrow the "Social Security earnings test" not-modeled bullet to match what T021 now describes as modeled — depends on T021
- [X] T023 [P] Add figure-verification table rows for `SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA` and `SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR` to `docs/BRD.md`'s figure-verification material — depends on T003
- [X] T024 [P] Check `docs/SOLUTION_ARCHITECTURE.md` for whether `mechanics.social_security_benefit`'s component description needs a one-line mention of the new operations — depends on Phase 2
- [X] T025 [P] Check `README.md` for whether test counts need updating — depends on Phases 2-5
- [X] T026 Run full quickstart.md validation end-to-end
- [X] T027 Run `pytest tests/` and confirm green (no other package touched — no new scenario input, no BFF/Streamlit change)
- [ ] T028 `bd close rp-acq` with a summary of what was modeled and where (mechanics/social_security_benefit.py, comparison/projection.py, docs/BRD.md)

---

## Dependencies & Execution Order

- **Setup (T001)**: no dependencies.
- **Foundational (T002-T008)**: blocks every user story — the two new mechanics operations themselves.
- **User Story 1 (T009-T015)**: depends on Foundational; withholding wiring, first half of the MVP.
- **User Story 2 (T016-T019)**: depends on User Story 1's `cumulative_earnings_test_months_withheld` scaffold (T011, T012) — recredit wiring, second half of the MVP. Both US1 and US2 are P1: the issue's own acceptance criteria treats withholding without recredit as equally wrong as modeling nothing, so neither alone is a complete MVP.
- **User Story 3 (T020)**: depends on T012 — test only, FRA-year rate selection is already correct from T004/T007.
- **Polish (T021-T028)**: docs/validation — can start once Phase 4 lands.

## Implementation Strategy

### MVP First

Phases 1-4 (through T019) deliver rp-acq's full core ask: correct near-term withholding **and** its
FRA recredit, together — per the issue's own acceptance criteria, shipping only one half would
mis-state the household's finances in the opposite direction. Phase 5 is a test-only confirmation of
behavior already correct from Phase 2's `compute_earnings_test_withholding()`. Phase 6 completes the
docs vertical every prior SS feature (`016`, `017`) established as this project's norm.
