---

description: "Task list template for feature implementation"
---

# Tasks: Year-by-Year Results Walkthrough

**Input**: Design documents from `/specs/028-results-walkthrough/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/reporting-narrative-api.md](./contracts/reporting-narrative-api.md),
[quickstart.md](./quickstart.md)

**Tests**: Included. The spec's own Success Criteria (SC-001–SC-005) and the parent bead's
design directly call for `tests/unit/reporting/test_narrative.py` mirroring
`test_aggregation.py`, plus BFF and UI test coverage — these aren't optional TDD scaffolding
here, they're acceptance-criteria deliverables.

**Organization**: Tasks are grouped by user story (US1/US2/US3 from spec.md, priority order).
US2 and US3 build on the same `narrative.py` module US1 creates rather than adding a separate
module — each still has its own independent test criteria and can be verified on its own once
its tasks are done.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3 — Setup/Foundational/Polish tasks carry no story label

## Path Conventions

Existing repo layout (see plan.md Project Structure) — no new top-level directory:
`src/retirement_planner/reporting/`, `services/bff/src/rp_bff/`, `apps/streamlit_ui/`, each with
its own `tests/`.

---

## Phase 1: Setup

**Purpose**: Scaffold the two brand-new files this feature adds (everything else extends an
existing file). No new dependency is added to any of the three packages (plan.md Technical
Context) — nothing else to configure.

- [X] T001 [P] Create `src/retirement_planner/reporting/narrative.py` with a module docstring
      describing its purpose (mirrors `aggregation.py`'s own docstring style — see
      [research.md](./research.md) §1-§3) and the standard imports it will need
      (`from __future__ import annotations`, `from dataclasses import dataclass`,
      `from .models import NarrativeEntry, RunNarrative, YearStory`, `member_age_in_tax_year`/
      `deemed_rmd_owner` from `retirement_planner.comparison`, `WITHDRAWAL_STRATEGIES` from
      `retirement_planner.mechanics`, `SimulationRun`/`PlanProjection`/`PlanYearProjection` type
      imports as needed). No function bodies yet.
- [X] T002 [P] Create `apps/streamlit_ui/pages/4_Walkthrough.py` with a module docstring (mirrors
      `3_Compare.py`'s header style), `import streamlit as st`, and a page title/header call. No
      rendering logic yet.

**Checkpoint**: Both new files exist and import cleanly (`python -c "import ..."` / Streamlit
page list shows "Walkthrough").

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared data shapes every user story's tasks read or write. Must land before any
US1/US2/US3 task.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add `NarrativeEntry`, `YearStory`, and `RunNarrative` dataclasses to
      `src/retirement_planner/reporting/models.py`, exactly per
      [data-model.md](./data-model.md) — `YearStory.unverified_figure_names` gets
      `field(default_factory=list)` (populated in US3, not required for this task). Add a
      docstring pointing back to `data-model.md` matching `SummaryStatistics`'s own convention.
- [X] T004 Export `NarrativeEntry`, `YearStory`, `RunNarrative` from
      `src/retirement_planner/reporting/__init__.py`'s import list and `__all__` (depends on T003).

**Checkpoint**: `from retirement_planner.reporting import NarrativeEntry, YearStory, RunNarrative`
succeeds. User story implementation can now begin.

---

## Phase 3: User Story 1 - Step through a representative year-by-year story (Priority: P1) 🎯 MVP

**Goal**: A user who completed a Run Simulation can open the new Walkthrough page and read a
plain-language story for every plan year of one representative path, stepping through it three
years at a time with Next/Previous.

**Independent Test**: Run a simulation, open the Walkthrough page, and step from the first to
the last batch of plan years — every year shows a non-empty story alongside its existing numeric
detail, and the controls disable at the first/last batch.

### Implementation for User Story 1

- [X] T005 [US1] Implement `select_representative_path(run: SimulationRun) -> int` in
      `src/retirement_planner/reporting/narrative.py` per
      [contracts/reporting-narrative-api.md](./contracts/reporting-narrative-api.md): returns 0
      immediately when `len(run.path_results) == 1`; otherwise the index of the path whose
      `outcome.ending_balance` is closest to `run.percentile_bands[-1].percentiles[0.50]`, ties
      broken by lowest index (FR-001, research.md §5).
- [X] T006 [US1] Implement `build_year_stories(projection, household, reference_tax_year) ->
      list[YearStory]` in `src/retirement_planner/reporting/narrative.py`: walks
      `projection.years` pairwise (plan year 1 compared against its own starting values),
      detecting each v1 driver per the field-by-field table in
      [research.md](./research.md) §3 — RMD start (`member_rmd_amounts` 0→nonzero per member),
      SS claiming (`member_social_security_benefits` 0→nonzero per member), Roth conversion
      (`mechanics.conversion.amount_converted > 0`, every occurrence), withdrawal-source change
      (`mechanics.withdrawal_plan.sequence_withdrawals` account_type 0↔nonzero transitions,
      citing `WITHDRAWAL_STRATEGIES[strategy.withdrawal_strategy]`), tax change (`federal_tax
      .federal_tax_owed + state_tax.state_tax_owed`, ≥15% YoY per spec.md Clarifications),
      IRMAA start/basis-switch (`irmaa.surcharge_owed` 0→nonzero, `irmaa.income_basis` change),
      survivor death (`filing_status` married→single transition), shortfall (`shortfall > 0`,
      every occurrence) — plus a single `driver_key="baseline"` `NarrativeEntry` when none of the
      above fired that year (FR-005). Builds each year's `member_ages` via the existing
      `member_age_in_tax_year()`. Leaves `unverified_figure_names` at its default `[]` for now
      (populated in T017/US3). Depends on T005 only insofar as both live in the same new file —
      no functional dependency between them.
- [X] T007 [US1] Implement `build_narrative_for_run(run, household, reference_tax_year) ->
      RunNarrative` in `src/retirement_planner/reporting/narrative.py`, composing T005 + T006
      over `run.path_results[selected_path_index]` (depends on T005, T006).
- [X] T008 [US1] Export `select_representative_path`, `build_year_stories`,
      `build_narrative_for_run` from `src/retirement_planner/reporting/__init__.py` (depends on
      T007).
- [X] T009 [US1] In `services/bff/src/rp_bff/routes/simulations.py`'s `run_simulation_route()`,
      call `build_narrative_for_run(run, household=context.household,
      reference_tax_year=body.reference_tax_year)` once (selected-path-only, no per-path loop)
      and add `"narrative": to_jsonable(narrative)` to the returned response dict, alongside the
      existing `run`/`summary`/`account_detail` keys (FR-008; depends on T008).
- [X] T010 [US1] Implement `apps/streamlit_ui/pages/4_Walkthrough.py`'s main body: if
      `"run_last_result"` not in `st.session_state`, render guidance to run a simulation first
      (FR-013) and stop; otherwise read `st.session_state["run_last_result"]["narrative"]`
      (no new HTTP call, research.md §7), maintain
      `st.session_state["walkthrough_batch_index"]` (reset to 0 whenever `run_last_result`
      changes — compare against a stored last-seen run identity, e.g. `id()` or a hash of the
      result, the same way other pages key off `run_last_result`), and render the current batch
      of up to 3 consecutive `YearStory` entries (FR-009): each year's `plan_year`, `member_ages`,
      and every `NarrativeEntry.label`/`explanation`, followed by that plan year's existing
      numeric detail (reuse `render_account_table()` filtered/scoped to the shown years, or the
      existing per-year fields already in `run["path_results"][selected_path_index]["years"]`).
      Depends on T009 (needs the `narrative` field present in the response shape) and T002.
- [X] T011 [US1] Add Next/Previous `st.button`s to `4_Walkthrough.py` that advance/retreat
      `walkthrough_batch_index` by one batch, disabled (`disabled=True`) at the first/last batch
      respectively (FR-010; depends on T010).

### Tests for User Story 1

- [X] T012 [P] [US1] In `tests/unit/reporting/test_narrative.py` (new, mirrors
      `test_aggregation.py`'s fixture style — synthetic `PlanProjection`/`PlanYearProjection`
      built via `run_plan_projection()`, then assembled into a `SimulationRun`): one test per v1
      driver asserting it fires exactly on its transition plan year and not on any other year
      (research.md §2/§3), plus a test that a year with no detected driver gets exactly one
      `baseline` entry (FR-005).
- [X] T013 [P] [US1] In the same `tests/unit/reporting/test_narrative.py`: assert
      `build_narrative_for_run()`'s `years` covers every plan year of the selected path with no
      gaps/duplicates (FR-002), and that `select_representative_path()` returns 0 for a
      single-path `SimulationRun` without needing non-degenerate `percentile_bands`.
- [X] T014 [P] [US1] In `services/bff/tests/integration/test_bff_lifecycle.py`: extend/add a test
      (mirrors `test_run_simulation_response_includes_account_detail_shaped_per_account`'s style)
      asserting `POST /simulations`'s response includes a `narrative` key shaped per
      [contracts/reporting-narrative-api.md](./contracts/reporting-narrative-api.md), and that
      `run`/`summary`/`account_detail` are byte-identical to before this feature (FR-014).
- [X] T015 [P] [US1] Create `apps/streamlit_ui/tests/unit/test_walkthrough.py` (mirrors
      `test_account_table.py`'s style — pure-rendering helpers, no live Streamlit script
      context): assert batch slicing produces batches of 3 plan years (last batch shorter when
      the remainder isn't a multiple of 3), and that Next/Previous availability matches the
      current batch index (FR-010).

**Checkpoint**: User Story 1 is fully functional and independently testable — run a simulation,
open Walkthrough, read every year's story, step through with Next/Previous.

---

## Phase 4: User Story 2 - Trust that the story matches a specific, reproducible path (Priority: P2)

**Goal**: Re-running an identical scenario+seed selects the same representative path and
produces byte-identical narrative text every time.

**Independent Test**: Call `build_narrative_for_run()` twice with two `SimulationRun`s produced
from an identical scenario configuration and seed; diff `selected_path_index` and `years`.

No new production code is required for this story — `select_representative_path()` and
`build_year_stories()` (T005/T006) are already pure functions over already-deterministic input,
so reproducibility is a property to verify, not build. This story is test-only.

### Tests for User Story 2

- [X] T016 [P] [US2] In `tests/unit/reporting/test_narrative.py`: build two `SimulationRun`s from
      identical scenario configuration/seed (reusing `run_plan_projection()`/`run_simulation()`
      fixtures), call `build_narrative_for_run()` on each, and assert `selected_path_index` is
      equal and `years == years` (dataclass equality) between the two results (FR-006/SC-002).
      Also add a tie-break test: construct a `SimulationRun` where two paths have equal distance
      from the median ending balance and assert `select_representative_path()` returns the lower
      index deterministically (FR-001, spec.md Assumptions).
- [X] T017 [P] [US2] In `services/bff/tests/integration/test_bff_lifecycle.py`: extend/add a test
      (mirrors `test_identical_run_requests_produce_identical_results`'s style) asserting two
      identical `POST /simulations` requests produce a byte-identical `narrative` field in their
      responses.

**Checkpoint**: User Stories 1 AND 2 both verified — the walkthrough is not just present but
provably reproducible.

---

## Phase 5: User Story 3 - See which numbers in the story are still unverified (Priority: P3)

**Goal**: A figure already flagged unverified elsewhere in the tool stays visibly flagged when
it appears in a plan year's story on the Walkthrough page.

**Independent Test**: Run a scenario known to touch a currently-unverified figure (e.g., NC
Bailey exclusion, or `historical_bootstrap` generation mode), open Walkthrough, and confirm the
same figure name is flagged there as on the existing Run Simulation results page.

### Implementation for User Story 3

- [X] T018 [US3] In `src/retirement_planner/reporting/aggregation.py`, rename
      `_unverified_figure_names` to public `unverified_figure_names` (behavior unchanged); update
      every call site inside `aggregation.py` to the new name (research.md §4, mirrors 006's own
      `_member_age_in_tax_year` → `member_age_in_tax_year` precedent).
- [X] T019 [US3] Export `unverified_figure_names` from
      `src/retirement_planner/reporting/__init__.py`'s import list and `__all__` (depends on
      T018).
- [X] T020 [US3] In `src/retirement_planner/reporting/narrative.py`'s `build_year_stories()`
      (T006), set each `YearStory.unverified_figure_names = unverified_figure_names(year
      .figures_used)` for that plan year (depends on T019, T006).
- [X] T021 [US3] In `apps/streamlit_ui/pages/4_Walkthrough.py`, call the existing
      `render_verification_indicator()` (import from `rp_ui.verification`, same as
      `2_Run_Simulation.py`/`3_Compare.py`) once per shown `YearStory`, passing that year's own
      `unverified_figure_names` — scoped per year, not one page-level call over the whole run
      (FR-011; depends on T010, T020).

### Tests for User Story 3

- [X] T022 [P] [US3] In `tests/unit/reporting/test_narrative.py`: assert a plan year whose
      `figures_used` includes an unverified figure surfaces that figure's name in its
      `YearStory.unverified_figure_names`, and a plan year with only verified figures gets an
      empty list (mirrors `test_aggregation.py`'s own unverified-figure tests).
- [X] T023 [P] [US3] In `apps/streamlit_ui/tests/unit/test_walkthrough.py`: assert the page's
      rendering calls `render_verification_indicator()` with each shown year's own
      `unverified_figure_names` list (mirrors `test_verification.py`'s style of asserting on
      `st.success`/`st.warning` calls).

**Checkpoint**: All three user stories independently functional — the walkthrough exists,
is reproducible, and never presents an unverified figure as settled.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Living-documentation updates and final whole-feature validation (project CLAUDE.md's
"update these in the same change" rule; SC-005).

- [X] T024 [P] Update `README.md`: new `4_Walkthrough.py` page and the new `narrative` field on
      `POST /simulations` (per the project's living-documentation convention — new
      page/route/test count).
- [X] T025 [P] Update `docs/SOLUTION_ARCHITECTURE.md`: new `narrative.py` module, the new
      `narrative` response field, and the new Walkthrough page in the relevant C4 views. No
      `docs/BRD.md` change (no new regulated figure, tax rule, or math — spec.md Assumptions).
- [X] T026 Run [quickstart.md](./quickstart.md) end-to-end (direct call, reproducibility check,
      curl against the BFF, manual UI walkthrough) and confirm every step's expected outcome.
- [X] T027 Run all four test suites and confirm zero regression anywhere outside this feature's
      own new tests (SC-005): `pytest tests/`, `pytest services/bff/tests/`,
      `pytest apps/streamlit_ui/tests/`, and `cd e2e && ../.venv/bin/python3.12 -m pytest -q`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001/T002 can start immediately, in parallel.
- **Foundational (Phase 2)**: Depends on Setup (T003 extends `models.py`, independent of T001/
  T002 but logically comes after the new files exist) — BLOCKS every user story.
- **User Story 1 (Phase 3)**: Depends on Foundational (T003/T004). Nothing else blocks it — the
  MVP slice.
- **User Story 2 (Phase 4)**: Depends on User Story 1's T005/T006 existing (tests exercise them
  directly) — no new production code of its own.
- **User Story 3 (Phase 5)**: Depends on User Story 1's T006/T010 (extends the same functions/
  page) and introduces its own new production tasks (T018-T021).
- **Polish (Phase 6)**: Depends on Phases 3-5 all being complete.

### Within Each User Story

- US1: T005 → T006 → T007 → T008 → T009 → T010 → T011 (mostly sequential — same file,
  `narrative.py`, then a dependent BFF edit, then a dependent UI page); T012-T015 (tests) can run
  in parallel with each other once their respective implementation tasks land, since each targets
  a different test file.
- US2: T016, T017 are independent test-file edits — parallel.
- US3: T018 → T019 → T020 → T021 (sequential — each depends on the previous); T022, T023 parallel
  once T020/T021 land.

### Parallel Opportunities

- T001 + T002 (Setup, different files).
- T012 + T013 + T014 + T015 (US1 tests, four different test files) once their implementation
  dependencies land.
- T016 + T017 (US2, two different test files).
- T022 + T023 (US3 tests, two different test files).
- T024 + T025 (Polish, two different doc files).

---

## Parallel Example: User Story 1 tests

```bash
# Once T005-T011 have landed, launch all US1 test tasks together:
Task: "Driver-by-driver + baseline tests in tests/unit/reporting/test_narrative.py"
Task: "Path-coverage + single-path-selection tests in tests/unit/reporting/test_narrative.py"
Task: "narrative field shape/unchanged-fields test in services/bff/tests/integration/test_bff_lifecycle.py"
Task: "Batch slicing + Next/Previous availability tests in apps/streamlit_ui/tests/unit/test_walkthrough.py"
```

(T012/T013 share a file, so within this pair run them sequentially even though both are marked
[P] relative to the *other* test files — the [P] marker means "no cross-file conflict with the
rest of the batch," not "no file overlap within it.")

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002).
2. Complete Phase 2: Foundational (T003-T004) — CRITICAL, blocks everything else.
3. Complete Phase 3: User Story 1 (T005-T015).
4. **STOP and VALIDATE**: run a simulation, open Walkthrough, step through every year — matches
   Independent Test above.
5. Demo if ready — this alone delivers rp-bm8.1's core value (a readable year-by-year story),
   even before reproducibility/verification-flagging tests are added.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. User Story 1 → validate independently → MVP.
3. User Story 2 → validate independently (pure test addition, low risk) → confidence in
   reproducibility.
4. User Story 3 → validate independently → confidence no unverified figure slips through.
5. Polish → docs + full-suite regression check → ready to close rp-bm8.1.

---

## Notes

- [P] tasks touch different files with no incomplete dependency between them.
- Every task above cites the exact file it touches — no task should require guessing a path.
- Commit after each task or logical group (per this repo's conservative git policy — do not
  push without explicit authority, per CLAUDE.md's Agent Context Profiles).
- Stop at any checkpoint to validate a story independently before moving to the next.
- P2's AI-rewritten narrative (rp-bm8.2) is out of scope for every task above — nothing here
  reaches for a language model or new dependency.
