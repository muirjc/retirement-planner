---

description: "Task list for 026-advanced-simulation-options"
---

# Tasks: Advanced Simulation Options (Historical Bootstrap + Stress Overlay)

**Input**: Design documents from `/specs/026-advanced-simulation-options/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — mirrors `rp-9vl`'s own precedent (integration tests in
`test_bff_lifecycle.py`, AppTest-driven UI tests in `test_app_pages.py`) for an opt-in
Monte-Carlo-only field.

**Organization**: Both capabilities share one BFF call site (`generate_configured_return_paths()`)
and one pair of request classes, so Phase 2 (Foundational) carries the full BFF-layer wiring for
*both* fields together (they can't be sensibly split — a request already flows through the shared
helper regardless of which of the two it sets). Each user story's own phase is then the
user-facing piece specific to that capability: UI controls + acceptance-scenario-level tests.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Confirm `pytest services/bff/tests/` and `pytest apps/streamlit_ui/tests/` both pass on `026-advanced-simulation-options` before any change (baseline for SC-003)

---

## Phase 2: Foundational (blocks every user story)

- [X] T002 [P] Add `StressScenarioRequest` (magnitude, duration_years, start_plan_year) to `services/bff/src/rp_bff/schemas.py` (data-model.md)
- [X] T003 [US-shared] In `services/bff/src/rp_bff/resolution.py`: import `GenerationMode`, `StressScenario`, `ReturnPath`, `generate_return_paths`, `generate_historical_bootstrap_paths`, `apply_stress_scenario` from `retirement_planner.simulation`; implement `generate_configured_return_paths(context, horizon_years, start_plan_year, generation_mode, historical_block_length, stress_scenario)` (contracts/bff-api.md, research.md Decisions 1-2) — depends on nothing beyond existing resolution.py
- [X] T004 [US-shared] Add `invalid_simulation_options_error(exc: ValueError) -> HTTPException` (422, `{"error": "invalid_simulation_options", "detail": str(exc)}`) to `resolution.py` (research.md Decision 5) — depends on T003
- [X] T005 [P] [US-shared] Unit tests for `generate_configured_return_paths()` in `services/bff/tests/unit/test_resolution.py`: `generation_mode="parametric"` (default) produces the same paths `generate_return_paths()` would directly; `generation_mode="historical_bootstrap"` produces paths whose `figures_used` includes `HISTORICAL_RETURNS` usage; a non-`None` `stress_scenario` overrides the configured window regardless of generation_mode; `stress_scenario=None` (default) leaves paths unmodified; a `ValueError` from either engine call propagates unchanged — depends on T003
- [X] T006 [US-shared] Add `generation_mode: GenerationMode = "parametric"`, `historical_block_length: int = 10`, `stress_scenario: StressScenarioRequest | None = None` to `SimulationRequest` in `services/bff/src/rp_bff/routes/simulations.py` (data-model.md) — depends on T002
- [X] T007 [US-shared] In `resolve_and_run_simulation()`, replace the direct `generate_return_paths()` call with `generate_configured_return_paths()` (converting `body.stress_scenario` to a core `StressScenario` when not `None`), wrapped in `try/except ValueError: raise invalid_simulation_options_error(exc)` — depends on T004, T006
- [X] T008 [US-shared] Add the identical three fields to `ComparisonRequest` in `services/bff/src/rp_bff/routes/comparisons.py` — depends on T002
- [X] T009 [US-shared] In `resolve_and_compare_simulated()`, same substitution as T007 — `resolve_and_compare_deterministic()` is NOT touched (FR-007) — depends on T004, T008
- [X] T010 [P] [US-shared] Add `InvalidSimulationOptionsError(RpUiError)` (holds `detail: str`) to `apps/streamlit_ui/src/rp_ui/errors.py`, mirroring `UnknownReferenceValueError`'s own shape, and a matching `if error == "invalid_simulation_options":` branch in `apps/streamlit_ui/src/rp_ui/api_client.py`'s `_raise_for_error_response()` — depends on nothing beyond existing files

**Checkpoint**: Both capabilities fully correct and error-handled at the BFF layer (`POST
/simulations`, `POST /comparisons/simulated`). No UI control yet — quickstart.md §1-6 all pass via
direct API calls; no Streamlit page shows either option yet.

---

## Phase 3: User Story 1 - Stress-test a plan against a bad early sequence of returns (Priority: P1) 🎯 MVP

**Goal**: A household can configure and run a stress-tested simulation or comparison from the Run
Simulation / Compare pages themselves.

**Independent Test**: quickstart.md §1 — configuring a stress scenario in the UI and running
produces a measurably worse success rate than the same run without it.

### Implementation for User Story 1

- [X] T011 [US1] In `apps/streamlit_ui/pages/2_Run_Simulation.py`'s existing "Advanced overrides" expander: add a `st.checkbox("Apply a sequence-of-returns stress overlay", key="run_apply_stress", ...)` plus `st.number_input` fields for magnitude/duration_years/start_plan_year (keys `run_stress_magnitude`/`run_stress_duration_years`/`run_stress_start_plan_year`), with help text explaining sequence-of-returns risk (mirrors the expander's existing help-text density) — depends on Phase 2
- [X] T012 [US1] `_build_run_body()`: add `"stress_scenario": {...}` only when `run_apply_stress` is checked (mirrors `run_override_advanced`'s own conditional-inclusion pattern for `n_paths`/`seed`/`plan_to_age`) — depends on T011
- [X] T013 [US1] Catch `InvalidSimulationOptionsError` in `2_Run_Simulation.py`'s existing `except` chain and show `err.detail` via `st.error()` — depends on T010, T012
- [X] T014 [US1] In `apps/streamlit_ui/pages/3_Compare.py`, add a NEW "Advanced overrides" expander (none exists today) inside the existing `if st.session_state.get("compare_engine") != "Deterministic":` block (immediately after the `survival_adjusted` checkbox, research.md Decision 6), with the identical stress-overlay checkbox + three number_inputs (keys prefixed `compare_`) — depends on Phase 2
- [X] T015 [US1] `_build_body()`: add `"stress_scenario"` via the same `.get(..., False)`-safe pattern `survival_adjusted` already uses (so a Deterministic-engine submission, where the expander never rendered, doesn't KeyError) — depends on T014
- [X] T016 [US1] Catch `InvalidSimulationOptionsError` in `3_Compare.py`'s existing `except` chain — depends on T010, T015
- [X] T017 [P] [US1] Integration tests in `services/bff/tests/integration/test_bff_lifecycle.py`: a stressed `/simulations` run has a measurably lower `success_rate` than the identical unstressed run (quickstart.md §1); a stress window extending past `plan_to_age` returns 422 `invalid_simulation_options` (quickstart.md §2); a stressed `/comparisons/simulated` request applies identically to every candidate (quickstart.md §5); `/comparisons/deterministic` is unaffected by a `stress_scenario` field present in the body (quickstart.md §6, FR-007) — depends on T007, T009
- [X] T018 [P] [US1] AppTest UI tests in `apps/streamlit_ui/tests/integration/test_app_pages.py`, mirroring the existing `survival_adjusted` test block's structure: unchecked `run_apply_stress` sends no `stress_scenario` key at all; checking it and filling the three fields sends the matching nested object; the equivalent two cases for `3_Compare.py`'s new expander (rendered only for Monte Carlo engine); a 422 `invalid_simulation_options` response renders the specific message — depends on T012, T013, T015, T016

**Checkpoint**: User Story 1 fully functional — the MVP; a household can stress-test a plan
end-to-end without leaving the app.

---

## Phase 4: User Story 2 - Probe how much the parametric assumption itself matters (Priority: P2)

**Goal**: A household can select historical-bootstrap generation mode from the Run Simulation /
Compare pages and see the result flagged as relying on an unverified data source.

**Independent Test**: quickstart.md §3 — selecting historical-bootstrap mode and running shows
`"historical_annual_real_returns"` in the response's `unverified_figure_names`.

### Implementation for User Story 2

- [X] T019 [US2] In `2_Run_Simulation.py`'s "Advanced overrides" expander: add `st.selectbox("Return generation mode", options=["parametric", "historical_bootstrap"], key="run_generation_mode", ...)` and `st.number_input("Historical block length (years)", key="run_historical_block_length", ...)`, with help text stating plainly that the historical series is a synthetic placeholder, not real market history (FR-006, mirrors `survival_adjusted`'s own disclosed-caveat precedent) — depends on Phase 2
- [X] T020 [US2] `_build_run_body()`: add `"generation_mode"` and `"historical_block_length"` (both always sent — no conditional gate, since they always have a meaningful default) — depends on T019
- [X] T021 [US2] Add the identical selectbox + number_input to `3_Compare.py`'s new Advanced-overrides expander (from T014), same Monte-Carlo-only gate — depends on T014
- [X] T022 [US2] `_build_body()`: same two always-sent fields — depends on T021
- [X] T023 [P] [US2] Integration tests in `test_bff_lifecycle.py`: `generation_mode="historical_bootstrap"` on `/simulations` includes `"historical_annual_real_returns"` in `summary.unverified_figure_names` (quickstart.md §3); `historical_block_length=0` returns 422 `invalid_simulation_options` (quickstart.md §4); the default (`generation_mode` omitted) leaves `unverified_figure_names` unaffected by this feature (SC-003) — depends on T007, T009
- [X] T024 [P] [US2] AppTest UI tests: the generation-mode selectbox defaults to `"parametric"` and is always sent; selecting `"historical_bootstrap"` and running shows the unverified-figure warning (mirrors the existing `survival_curve_primary` warning assertion at T018's sibling test); the equivalent for `3_Compare.py` — depends on T020, T022

**Checkpoint**: Both user stories independently functional — the full BFF/UI parity gap `rp-xxp`
found is closed.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T025 Update `docs/BRD.md` §6.8: remove the "Not yet exposed through the BFF or Streamlit UI" sentences from both the historical-bootstrap and stress-overlay bullets, replacing with what's now exposed and how (the Advanced-overrides expander, Monte-Carlo-only, unverified-figure flagging)
- [X] T026 Update `docs/BRD.md` §7: close the "rp-741, rp-2bn... scheduled to expose both" Known Limitations bullet — depends on T025
- [X] T027 [P] Check `docs/SOLUTION_ARCHITECTURE.md` for whether the BFF/Streamlit component descriptions need a one-line mention (no new package/route — likely small, confirm) — depends on Phase 2
- [X] T028 [P] Check `README.md` for whether test counts need updating — depends on Phases 2-4
- [X] T029 Run full quickstart.md validation end-to-end
- [X] T030 Run `pytest services/bff/tests/` and `pytest apps/streamlit_ui/tests/`, confirm green; confirm `pytest tests/` (core) is untouched/still green (no core-library change in this feature)
- [X] T031 `bd close rp-741 rp-2bn` with a summary of what was modeled and where

---

## Dependencies & Execution Order

- **Setup (T001)**: no dependencies.
- **Foundational (T002-T010)**: blocks every user story — both capabilities' full BFF-layer wiring, since they share one call site and can't be meaningfully split at that layer.
- **User Story 1 (T011-T018)**: depends on Foundational; stress-overlay UI, the MVP.
- **User Story 2 (T019-T024)**: depends on Foundational and on Phase 3's `3_Compare.py` expander existing (T014) — historical-bootstrap UI.
- **Polish (T025-T031)**: docs/validation — can start once Phase 4 lands.

## Implementation Strategy

### MVP First

Phases 1-3 (through T018) deliver rp-2bn's full ask (a household can stress-test a plan end-to-end
through the app) plus all of the shared BFF-layer plumbing rp-741 also needs. Phase 4 is then a
comparatively small, mostly-additive UI-only change (T019-T024) reusing every piece of Phase 2's
machinery, closing rp-741. Phase 5 completes the docs vertical every prior feature in this project
establishes as the norm.
