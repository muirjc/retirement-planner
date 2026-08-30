---

description: "Task list template for feature implementation"
---

# Tasks: Per-Account Year-by-Year Projection Detail

**Input**: Design documents from `/specs/015-per-account-projection-detail/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md).

**Tests**: Included. Not independently requested in spec.md, but the constitution's Unit-test-coverage gate plus plan.md's own Development Workflow section require invariant tests for this feature's new arithmetic (sums-to-pooled-total, exactness in the common case, zero-division safety) — mirroring `011`'s own test precedent for its analogous fixed-share RMD logic.

**Organization**: Tasks are grouped by user story (spec.md's US1, US2), with a shared Foundational phase for the engine/reporting-layer changes both stories build on — per plan.md's own layered design (Phase 1 engine → Phase 2 reporting → Phase 3 BFF → Phase 4 UI), reorganized here by user-facing story rather than technical layer, as this workflow requires.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with the other tasks in its immediate list (different files, no dependency on one another)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Where a task depends on an earlier task's output, that's called out inline as `(depends on T0xx)`

## Phase 1: Setup

**Purpose**: Establish a baseline — this feature is purely additive, so every currently-passing test must stay passing throughout.

- [X] T001 Run all four existing suites (`pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`, `cd e2e && ../.venv/bin/python3.12 -m pytest -q`) and record the baseline pass counts — every later task's own test run is judged against this baseline staying green, never regressing

**Checkpoint**: Baseline recorded — proceed to Foundational.

---

## Phase 2: Foundational

**Purpose**: The engine-level data retention and the new attribution module both user stories consume — neither US1 nor US2 can be implemented without this landing first (plan.md's Phase 1 + Phase 2, data-model.md).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `member_rmd_amounts: dict[str, float]`, `member_social_security_benefits: dict[str, float]`, `inherited_account_balances: dict[str, float]`, `inherited_account_distributions: dict[str, float]` (all `field(default_factory=dict)`) to `PlanYearProjection` in `src/retirement_planner/comparison/models.py` (data-model.md § PlanYearProjection extension)
- [X] T003 In `src/retirement_planner/comparison/projection.py`'s `run_plan_projection()` loop: capture the already-computed per-member `RmdResult`s into a dict before they're summed into `rmd_amount`; capture `_household_gross_social_security_benefit()`'s per-member amounts into a dict before they're summed; capture each inherited account's own balance/distribution at the existing per-inherited-account loop. Thread all four into the `PlanYearProjection(...)` construction. No existing field's value may change (depends on T002)
- [X] T004 [P] Extend `tests/unit/comparison/test_projection.py` with invariant assertions: `sum(member_rmd_amounts.values())` matches the pooled `mechanics.withdrawal_plan.rmd_drawn` when not shortfall-capped; `member_social_security_benefits` sums correctly and includes every member (even pre-claiming, at `0.0`); inherited-account snapshot dicts match the already-tested `InheritedAccountBalance` mutation from `012`/`013`'s own fixtures (depends on T003)
- [X] T005 [P] Create `src/retirement_planner/reporting/account_attribution.py`: `AccountShare`, `AccountYearDetail`, `PlanYearAccountDetail` dataclasses and `compute_account_shares(accounts) -> list[AccountShare]` per contracts/reporting-api.md — mirror `services/bff/src/rp_bff/resolution.py`'s `_traditional_ownership_shares()` zero-guard exactly (a zero-balance type gets every account's `fixed_share` fixed at `0.0`, never a `ZeroDivisionError`)
- [X] T006 In `src/retirement_planner/reporting/account_attribution.py`: implement `attribute_plan_projection(projection, shares) -> list[PlanYearAccountDetail]` per data-model.md's field-by-field derivation — ordinary-account balance/withdrawal via the flat `fixed_share` (research.md §2), traditional-account RMD via the exact per-member figure (T003's new field) sub-allocated only when a member owns more than one traditional account, inherited-account rows passed through exactly from T003's new fields with `attribution="independently_tracked"` (depends on T005, T003)
- [X] T007 Export `AccountShare`, `AccountYearDetail`, `PlanYearAccountDetail`, `compute_account_shares`, `attribute_plan_projection` from `src/retirement_planner/reporting/__init__.py` alongside the existing `summarize_run` etc. (depends on T006)
- [X] T008 [P] Create `tests/unit/reporting/test_account_attribution.py`: per-type `fixed_share`s sum to `1.0`; per-account ending/starting balances of a type sum to exactly that type's pooled `PlanYearProjection` balance; per-account withdrawal amounts of a type sum to exactly the pooled total; a member owning exactly one traditional account has that account's `rmd_amount` exactly equal to `member_rmd_amounts[member]` and `attribution == "independently_tracked"`; a member owning more than one gets `attribution == "fixed_share_of_pooled_total"` on the RMD sub-allocation; a zero-pooled-type account never divides by zero; inherited rows are always `"independently_tracked"` and never participate in share math (depends on T006)
- [X] T009 Create `services/bff/src/rp_bff/account_detail.py`: `build_account_detail_for_projection(scenario, projection)` and `build_account_detail_for_run(scenario, run, path_index)` (the latter bounds-checks `path_index` against `len(run.path_results)`, raising a `path_index_out_of_range` error mirroring `resolution.py`'s existing `unsupported_tax_year_error()` shape per contracts/bff-api.md) — both call T005/T006's `compute_account_shares()` + `attribute_plan_projection()` and return `to_jsonable()`-ready data (depends on T007)

**Checkpoint**: Foundation ready — `compute_account_shares()`/`attribute_plan_projection()`/`account_detail.py` all exist and are independently tested; US1 and US2 can now each wire them into their own route/page.

---

## Phase 3: User Story 1 - See each account's actual year-by-year detail on a simulation result (Priority: P1) 🎯 MVP

**Goal**: A user viewing a completed Monte Carlo simulation result sees, for one identified path, per-account balances/RMD/withdrawals and per-member Social Security, year by year (spec.md US1).

**Independent Test**: quickstart.md §1-4 (core-level invariants) plus §5's Run Simulation walkthrough — run a simulation for a scenario with two same-type accounts under different owners and a claiming member; confirm the new table and per-member Social Security figures render correctly.

### Implementation for User Story 1

- [X] T010 [US1] Add `detail_path_index: int | None = None` to `SimulationRequest` in `services/bff/src/rp_bff/schemas.py` (contracts/bff-api.md)
- [X] T011 [US1] In `services/bff/src/rp_bff/routes/simulations.py`'s `POST /simulations` handler: call T009's `build_account_detail_for_run(context.scenario, run, body.detail_path_index or 0)` and attach `"account_detail"` to the response; translate an out-of-range `path_index` into a 422 with the `path_index_out_of_range` shape (depends on T009, T010)
- [X] T012 [P] [US1] Extend `services/bff/tests/` (mirroring `test_resolution.py`'s/the existing simulation route tests' fixture style) with: response includes `account_detail` shaped per contracts/bff-api.md; omitted `detail_path_index` defaults to path 0; an out-of-range value returns 422 with the documented error shape (depends on T011)
- [X] T013 [P] [US1] Create `apps/streamlit_ui/src/rp_ui/account_table.py`: `render_account_table(account_detail: dict) -> None` — one `st.dataframe` row per `(plan_year, account_id)`, an `attribution` column rendered as a badge/caption reusing `verification.py`'s `render_verification_indicator()` disclosure idiom (no new visual convention) — a pure display function, computes nothing itself, matching `charts.py`'s existing convention
- [X] T014 [P] [US1] Create `apps/streamlit_ui/tests/unit/test_account_table.py`, mirroring `test_charts.py`'s literal-fixture-dict style (no network, no backend) (depends on T013)
- [X] T015 [US1] In `apps/streamlit_ui/pages/2_Run_Simulation.py`: call `render_account_table(result["account_detail"])` directly after the existing `render_verification_indicator(...)` call, inside the same results block; add a "Detail path index" `st.number_input` to the existing "Advanced overrides" expander, bounded by the last-known `n_paths` (depends on T013, T011)
- [X] T016 [US1] Extend `e2e/test_run_simulation_page.py` to assert the new account table renders after running a simulation (depends on T015)
- [X] T017 [US1] Run quickstart.md §1-4 against a real scenario (e.g. `b`) to confirm every invariant holds outside the unit-test fixtures too (depends on T006, T008)
- [X] T018 [US1] Manually complete quickstart.md §5's Run Simulation walkthrough: confirm the table, the per-attribution labeling, and the "Detail path index" override all behave as documented (depends on T015, T016)

**Checkpoint**: User Story 1 fully functional and independently testable — the MVP slice.

---

## Phase 4: User Story 2 - See the same year-by-year detail for each candidate being compared (Priority: P2)

**Goal**: A user comparing candidates sees each candidate's own year-by-year account detail, independently viewable, without losing the existing side-by-side summary comparison (spec.md US2).

**Independent Test**: quickstart.md §5's Compare walkthrough — run a comparison with 2+ candidates; confirm each candidate's own expandable detail is present and never mixed with another candidate's.

### Implementation for User Story 2

- [X] T019 [US2] Add `detail_path_index: int | None = None` to `ComparisonRequest` in `services/bff/src/rp_bff/schemas.py` (contracts/bff-api.md)
- [X] T020 [US2] In `services/bff/src/rp_bff/routes/comparisons.py`'s `compare_deterministic_route()`: before `result` goes out of scope, call T009's `build_account_detail_for_projection(context.scenario, projection)` once per `result.projections` entry and attach the list as `"account_detail"`, zipped in the same order as `"summaries"` (depends on T009, T019)
- [X] T021 [US2] In `compare_simulated_route()` (same file): call `build_account_detail_for_run(context.scenario, run, body.detail_path_index or 0)` once per `result.runs` entry (`compute_account_shares()` computed once per request, shared across candidates, per contracts/bff-api.md); translate the first out-of-range candidate's `path_index` into a 422, same shape as US1's (depends on T009, T019)
- [X] T022 [P] [US2] Extend `services/bff/tests/` for both comparison routes: response includes `account_detail` as one list per candidate, correctly ordered against `summaries`; the simulated route's out-of-range `detail_path_index` returns 422 (depends on T020, T021)
- [X] T023 [US2] In `apps/streamlit_ui/pages/3_Compare.py`: directly after the existing per-candidate `render_results_explanation()` loop, add `for s, detail in zip(summaries, result["account_detail"]): with st.expander(f"Year-by-year detail: {s.get('candidate_label')}"): render_account_table(detail)` — reuses US1's `account_table.py` component, no new UI component needed (depends on T013, T020, T021)
- [X] T024 [US2] Extend `e2e/test_compare_page.py` to assert every candidate's own expander/table renders, and that expanding one never shows another candidate's rows (depends on T023)

**Checkpoint**: Both user stories independently functional.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Confirm the whole feature together, and keep this project's living documentation current (CLAUDE.md's convention).

- [X] T025 Run all four suites again (`pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`, `cd e2e && ../.venv/bin/python3.12 -m pytest -q`) and confirm the T001 baseline count is met or exceeded in every suite — no regression, only additions
- [X] T026 [P] Review `docs/SOLUTION_ARCHITECTURE.md` per CLAUDE.md's living-documentation convention: add the new `reporting/account_attribution.py` module to the core-library Component diagram, and the new `account_detail` response field to the BFF Component diagram/route table — this feature introduces no new regulated figure or math, so `docs/BRD.md` needs no change (confirm, don't assume)
- [X] T027 Manually complete quickstart.md §5's full walkthrough (both Run Simulation and Compare) end-to-end against a real running app, per README.md's "Running the full stack" steps

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks both user stories** — neither US1 nor US2 has anything to wire into a route/page until `account_attribution.py` and `account_detail.py` exist.
- **User Stories (Phase 3-4)**: Both depend only on Phase 2, not on each other's route/page work — US2 reuses US1's `account_table.py` UI component (T013), so in practice implement US1 first even though nothing else forces that order.
- **Polish (Phase 5)**: Depends on whichever stories you're delivering being complete.

### Parallel Opportunities

- T004, T005, T008 (different files, Phase 2, each after its own prerequisite)
- T012, T013/T014 (different files, Phase 3)
- T022 (Phase 4, independent of UI work)
- Phase 3 (US1) and Phase 4 (US2) touch different BFF route files (`simulations.py` vs `comparisons.py`) and different UI pages (`2_Run_Simulation.py` vs `3_Compare.py`) — parallelizable across two people once T013 (US1's shared UI component) exists, since US2's T023 depends on it.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1)
2. **STOP and VALIDATE**: quickstart.md §1-4 and §5's Run Simulation walkthrough
3. This alone delivers the feature's full value for the most common way a user reaches this tool's output (running a single scenario's simulation) — Compare's own detail (US2) is additive on top.

### Incremental Delivery

1. Setup + Foundational → engine/reporting/BFF-assembly layer ready, fully unit-tested.
2. US1 → verify independently → MVP: Run Simulation page shows per-account detail.
3. US2 → verify independently → Compare page shows the same detail per candidate.
4. Polish → full-suite regression check, docs review.
