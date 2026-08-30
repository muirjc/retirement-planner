---

description: "Task list template for feature implementation"
---

# Tasks: Figure Verification (Placeholder Tax Figures)

**Input**: Design documents from `/specs/014-figure-verification/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [quickstart.md](./quickstart.md). No `contracts/` (plan.md — no public signature changes).

**Tests**: Included, though not strictly TDD-first. Tests aren't independently requested in spec.md, but the constitution's Verified-figure and Unit-test-coverage gates make a regression test *required* for every figure this feature touches — and this project's own precedent (`rp-6c5`'s `SINGLE_LIFE_EXPECTANCY_TABLE` fix) changes source and test together in one pass rather than writing a failing test first, since there's no new behavior to drive out, only a correction to an existing figure. Each story's tasks below follow that same source-then-test order.

**Organization**: Tasks are grouped by user story (spec.md's US1-US4), matching the epic's own Group A/B/C split (plan.md Summary).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with the other tasks in its immediate list (different files, no dependency on one another)
- **[Story]**: Which user story this task belongs to (US1-US4)
- Where a task depends on an earlier task's output, that's called out inline as `(depends on T0xx)`

## Phase 1: Setup

**Purpose**: Establish a baseline to diff against, since this feature's whole point is a traceable before/after (spec.md SC-005).

- [X] T001 Run the full suite (`pytest`) before any change and note the pass/fail baseline — every task in Phase 4-7 below that touches a downstream fixture is judged against this baseline, not against "did it pass," since some fixture values are *expected* to change (plan.md Constraints)

**Checkpoint**: Baseline recorded — proceed to Foundational.

---

## Phase 2: Foundational

**Purpose**: The one piece of prep shared by every later story — knowing in advance which existing tests hardcode a value one of these figures could shift, so each story's own "update affected fixtures" task isn't a blind search.

- [X] T002 Search `tests/unit/tax/`, `tests/unit/mechanics/`, `tests/unit/comparison/`, and `tests/unit/simulation/` for any hardcoded expected federal-tax, IRMAA-surcharge, HSA-limit, RMD-amount, or RMD-divisor value, and note (in the task's own PR/commit description, no new file needed) which tests are candidates for each of T019, T024, and T029 below

**Checkpoint**: Foundation ready. No other blocking prerequisites — `SourcedFigure` itself is unchanged (data-model.md) and each story below touches an independent set of production files, so US1-US4 can proceed in any order after this.

---

## Phase 3: User Story 1 - Statutory figures re-verified (Priority: P1) 🎯 MVP

**Goal**: `niit_rate`, both NIIT thresholds, and both Social Security provisional-income threshold pairs carry a real statutory citation and `verified=True`, with computed tax output unchanged (spec.md US1).

**Independent Test**: quickstart.md §1 — run a projection exercising NIIT and Social Security taxability; confirm both figures' `verified` flags and unchanged computed amounts.

### Implementation for User Story 1

- [X] T003 [P] [US1] Cross-check `niit_rate`, `niit_threshold_mfj`, `niit_threshold_single` against 26 U.S.C. §1411 (primary-source statute text); update `citation`, `last_verified`, and set `verified=True` for all three `SourcedFigure` instances in `src/retirement_planner/tax/niit.py`
- [X] T004 [P] [US1] Cross-check `ss_provisional_income_thresholds_mfj`/`_single` against 26 U.S.C. §86(c)(1)-(2) (primary-source statute text); update `citation`, `last_verified`, and set `verified=True` for both `SourcedFigure` instances in `src/retirement_planner/tax/social_security.py`
- [X] T005 [US1] Update `src/retirement_planner/tax/niit.py`'s module docstring — remove the "illustrative placeholders... `verified=False` reflects that honestly" paragraph now that T003 has verified them (depends on T003)
- [X] T006 [US1] Update `src/retirement_planner/tax/social_security.py`'s module docstring — remove the "still ship here as `verified=False` because they have not been cross-checked" sentence now that T004 has verified them (depends on T004)
- [X] T007 [P] [US1] Extend `tests/unit/tax/test_niit.py` with a test asserting `niit_rate`/`niit_threshold_mfj`/`niit_threshold_single` are all `verified is True` and spot-checking their values against the cited statute (depends on T003)
- [X] T008 [P] [US1] Extend `tests/unit/tax/test_social_security.py` with a test asserting both threshold figures are `verified is True` and spot-checking their values against the cited statute (depends on T004)
- [X] T009 [US1] Run quickstart.md §1 end-to-end and confirm every assertion passes (depends on T003-T008)

**Checkpoint**: User Story 1 fully verified and independently testable — 5 of the 8 figures done.

---

## Phase 4: User Story 2 - Annually-published figures re-verified (Priority: P2)

**Goal**: Federal brackets, IRMAA tiers, and HSA limits carry a citation naming a specific year/publication and `verified=True`, with any placeholder dollar figure corrected to match that publication (spec.md US2).

**Independent Test**: quickstart.md §2 — confirm all 5 figures' `verified` flags and that each citation names a real year.

### Implementation for User Story 2

- [X] T010 [P] [US2] Look up the most recently published IRS Revenue Procedure setting federal income tax bracket thresholds; correct `_MFJ_BRACKETS`/`_SINGLE_BRACKETS` literals in `src/retirement_planner/tax/federal.py` to match, update `citation`/`last_verified`/`verified=True` on `federal_brackets_mfj`/`_single`
- [X] T011 [P] [US2] Look up CMS.gov's published IRMAA premium tables for the most recent year; correct `_MFJ_TIERS`/`_SINGLE_TIERS` literals in `src/retirement_planner/tax/irmaa.py` to match, update `citation`/`last_verified`/`verified=True` on `irmaa_tiers_mfj`/`_single`
- [X] T012 [P] [US2] Look up the IRS Revenue Procedure announcing that year's HSA contribution limits; confirm or correct the `self_only`/`family`/`catch_up` literals in `src/retirement_planner/mechanics/hsa.py`, update `citation`/`last_verified`/`verified=True` on `hsa_contribution_limits`
- [X] T013 [US2] Update `src/retirement_planner/tax/federal.py`'s module docstring — replace "not asserted as the actual IRS Rev. Proc. 2026 figures... `verified=False` reflects that honestly" with the actual year/publication now cited (depends on T010)
- [X] T014 [US2] Update `src/retirement_planner/tax/irmaa.py`'s module docstring — replace the identical "not asserted as CMS's actual current tables" disclosure (depends on T011)
- [X] T015 [US2] Update `src/retirement_planner/mechanics/hsa.py`'s module docstring — replace the identical "not asserted as the IRS's actual current Rev. Proc. figures" disclosure (depends on T012)
- [X] T016 [P] [US2] Extend `tests/unit/tax/test_federal.py` with a test asserting `federal_brackets_mfj`/`_single` are `verified is True` and spot-checking the corrected thresholds against the cited Rev. Proc. (depends on T010)
- [X] T017 [P] [US2] Extend `tests/unit/tax/test_irmaa.py` with a test asserting `irmaa_tiers_mfj`/`_single` are `verified is True` and spot-checking the corrected tiers against the cited CMS.gov table (depends on T011)
- [X] T018 [P] [US2] Extend `tests/unit/mechanics/test_hsa.py` with a test asserting `hsa_contribution_limits` is `verified is True` and spot-checking the figures against the cited Rev. Proc. (depends on T012)
- [X] T019 [US2] Using T002's inventory, update any hardcoded expected-tax/expected-surcharge/expected-contribution fixture in `tests/unit/comparison/test_projection.py` and `tests/unit/comparison/test_compare.py` that shifts because T010/T011/T012 corrected a value — trace each changed expectation to the specific figure it now reflects (spec.md SC-005) (depends on T010, T011, T012, T002)
- [X] T020 [US2] Run quickstart.md §2 end-to-end and confirm every assertion passes (depends on T010-T019)

**Checkpoint**: User Stories 1 and 2 both independently verified — 8 of 8 figures re-cited, none requiring a schedule/coverage change yet.

---

## Phase 5: User Story 3 - RMD start age's 2033 step modeled (Priority: P3)

**Goal**: `rmd_start_age` is a genuine two-part schedule (73 before 2033, 75 from 2033 on), not a flat placeholder, cited against SECURE 2.0 (spec.md US3).

**Independent Test**: quickstart.md §3 — a household member turning the start age straddling 2033 gets the correct age each side of the step.

### Implementation for User Story 3

- [X] T021 [US3] Research 26 U.S.C. §401(a)(9)(C) as amended by SECURE 2.0 Act §107 to confirm the 2033 effective date and the age-75 figure; replace `RMD_START_AGE.schedule` in `src/retirement_planner/mechanics/rmd.py` with the two-part schedule from data-model.md (73 for `tax_year < 2033`, 75 for `tax_year >= 2033`), update `citation`/`last_verified`/`verified=True`
- [X] T022 [US3] Update `src/retirement_planner/mechanics/rmd.py`'s "Schedule note" docstring paragraph — it currently says the flat value is repeated because "this project's own documented figures don't yet model that second step"; rewrite it to describe the step now modeled, keeping the existing disclosure that birth-year-cohort modeling stays out of scope (research.md §3) (depends on T021)
- [X] T023 [US3] Add a 2033-straddle regression test to `tests/unit/mechanics/test_rmd.py`: assert `RMD_START_AGE.value_for_year(2032) == 73` and `value_for_year(2033) == 75`, assert `RMD_START_AGE.verified is True`, and assert `compute_rmd()` charges a 73-year-old an RMD in 2032 but not in 2033 (mirrors quickstart.md §3) (depends on T021)
- [X] T024 [US3] Using T002's inventory, update any hardcoded expected RMD amount in `tests/unit/comparison/test_projection.py`, `tests/unit/comparison/test_compare.py`, or `tests/unit/simulation/` for a household member whose first RMD year is 2033 or later, tracing each change to the corrected start age (spec.md SC-005) (depends on T021, T002)
- [X] T025 [US3] Run quickstart.md §3 end-to-end and confirm every assertion passes (depends on T021-T024)

**Checkpoint**: User Stories 1-3 independently verified. `rmd_start_age` no longer silently flat across a known future change.

---

## Phase 6: User Story 4 - Uniform Lifetime Table corrected and extended (Priority: P4)

**Goal**: `uniform_lifetime_table`'s divisors are correct and cover every age IRS Pub. 590-B Table III publishes, not just ages 72-100 (spec.md US4).

**Independent Test**: quickstart.md §4 — an RMD for a member aged 101+ now computes (no `KeyError`) using a divisor matching the published table.

### Implementation for User Story 4

- [X] T026 [US4] Cross-check every existing `_UNIFORM_LIFETIME_DIVISORS` entry (ages 72-100) in `src/retirement_planner/mechanics/rmd.py` against IRS Pub. 590-B, Appendix B, Table III (primary-source PDF — expect some entries wrong, per `rp-6c5`'s precedent where a sibling table was off by 1.7-2.8 across a third of its range); correct any wrong entry and extend coverage through the table's full published age range; update `citation`/`last_verified`/`verified=True` on `uniform_lifetime_table`
- [X] T027 [US4] Update `src/retirement_planner/mechanics/rmd.py`'s module docstring — remove `UNIFORM_LIFETIME_TABLE` from the "illustrative placeholder figures... `verified=False`" list (leave `JOINT_LIFE_TABLE`'s own separate disclosure untouched — plan.md "Deliberately out of scope") (depends on T026)
- [X] T028 [US4] Add regression tests to `tests/unit/mechanics/test_rmd.py`: assert `UNIFORM_LIFETIME_TABLE.verified is True`, spot-check several corrected divisors directly against the IRS Pub. 590-B PDF (mirroring `test_inherited_rmd.py`'s `rp-6c5` pattern), and add a case computing an RMD for a member aged 101+ that previously raised a plain `KeyError` (data-model.md) (depends on T026)
- [X] T029 [US4] Using T002's inventory, update any hardcoded expected RMD amount in `tests/unit/comparison/` or `tests/unit/simulation/` for a household member at an age whose divisor T026 corrected, tracing each change to the corrected divisor (spec.md SC-005) (depends on T026, T002)
- [X] T030 [US4] Run quickstart.md §4 end-to-end and confirm every assertion passes (depends on T026-T029)

**Checkpoint**: All 4 user stories independently verified — all 8 figures now `verified=True`, both structural gaps (2033 step, age coverage) closed.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Confirm the epic-level outcome, not just each story in isolation.

- [X] T031 Run the full suite (`pytest`) and confirm every diff from T001's baseline is traceable to a specific figure correction from T010, T011, T012, T021, or T026 (spec.md SC-005) — an unexplained diff is a bug in this feature, not an acceptable side effect
- [X] T032 Re-run the scenario that originally surfaced this work (scenario B) and confirm the Verification Indicator reports 0 of these 8 figures as unverified, down from 8 (spec.md SC-001)
- [X] T033 Close `rp-9wi.1` through `rp-9wi.7` in `bd` with each figure's actual primary-source finding as the close reason (mirroring `rp-6c5`'s own close-reason precedent), and confirm `bd show rp-9wi` reports 7/7 children complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. Its one task (T002) feeds T019/T024/T029 in later phases but doesn't block any story from *starting*.
- **User Stories (Phase 3-6)**: Each can start immediately after Phase 2 and touches an independent set of production files — **except** US3 (Phase 5) and US4 (Phase 6) both edit `src/retirement_planner/mechanics/rmd.py` (different symbols, `RMD_START_AGE` vs. `UNIFORM_LIFETIME_TABLE`/`_UNIFORM_LIFETIME_DIVISORS`) and both may touch the same downstream files in `tests/unit/comparison/`/`tests/unit/simulation/` (T024, T029) — run US3 and US4 sequentially, not concurrently by two different implementers, to avoid merge conflicts, even though they're logically independent.
- **Polish (Phase 7)**: Depends on every story you're delivering being complete — can run after just US1 (MVP) or after all four.

### Parallel Opportunities

- T003 and T004 (different files, Phase 3)
- T007 and T008 (different files, Phase 3, each after its own source task)
- T010, T011, and T012 (different files, Phase 4)
- T016, T017, and T018 (different files, Phase 4, each after its own source task)
- Phase 3 (US1) and Phase 4 (US2) can be worked by different people entirely in parallel — no shared files
- Phase 5 (US3) and Phase 6 (US4) share `rmd.py` — do not parallelize these two across people; either is fine to parallelize against Phase 3/4

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1)
2. **STOP and VALIDATE**: quickstart.md §1, `pytest tests/unit/tax/test_niit.py tests/unit/tax/test_social_security.py`
3. This alone removes 5 of the 8 unverified-figure findings with zero risk of a computed-output change — the cheapest, safest slice to ship first.

### Incremental Delivery

1. Setup + Foundational → baseline recorded, fixture inventory in hand.
2. US1 → verify independently → 5/8 done, MVP.
3. US2 → verify independently → 8/8 *re-cited*; this is the first phase that can shift computed output.
4. US3 → verify independently → the 2033 step is real, not silently flat.
5. US4 → verify independently → the age-100+ gap closes; all 8 figures fully done.
6. Phase 7 → epic-level confirmation, close all 7 beads.
