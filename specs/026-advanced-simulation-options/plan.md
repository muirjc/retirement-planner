# Implementation Plan: Advanced Simulation Options (Historical Bootstrap + Stress Overlay)

**Branch**: `026-advanced-simulation-options` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/026-advanced-simulation-options/spec.md`

## Summary

Adds one new shared `services/bff/src/rp_bff/resolution.py` helper,
`generate_configured_return_paths()`, that dispatches to
`retirement_planner.simulation.generate_return_paths()` (default) or
`generate_historical_bootstrap_paths()` (opt-in) and then optionally layers
`apply_stress_scenario()` on top — mirroring `build_survival_curves()`/
`validate_survival_curve_coverage()`'s own "shared resolution.py helper,
consumed identically by both `resolve_and_run_simulation()` and
`resolve_and_compare_simulated()`" precedent (rp-9vl) exactly. Both
`routes/simulations.py`'s `SimulationRequest` and `routes/comparisons.py`'s
`ComparisonRequest` gain three new optional fields each (duplicated per
those classes' existing no-shared-base convention):
`generation_mode` (default `"parametric"`), `historical_block_length`
(default `10`), and `stress_scenario` (a nested, schemas.py-shared
`StressScenarioRequest | None`, default `None`). A `ValueError` from either
engine call (bad block length, or a stress window past the horizon) is
translated to a 422 by one new shared error-translator, mirroring
`survival_curve_age_out_of_range_error()`'s own shape. Streamlit gains
matching controls: `2_Run_Simulation.py`'s existing "Advanced overrides"
expander gains the three new fields; `3_Compare.py` gains a brand-new
"Advanced overrides" expander (it has none today) holding only these three
fields, gated the same way its existing `survival_adjusted` checkbox
already is (`if compare_engine != "Deterministic"`).

## Technical Context

**Language/Version**: Python 3.11+ (existing project standard); FastAPI/Pydantic (BFF), Streamlit (UI)

**Primary Dependencies**: none new — every engine function this feature calls
(`generate_historical_bootstrap_paths()`, `apply_stress_scenario()`) already
exists and is tested in `retirement_planner.simulation` (`005-simulation-engine`)

**Storage**: N/A — no new scenario-configuration input; both options are
per-request-only, entered fresh each run/compare, the same way today's
existing `n_paths`/`seed`/`plan_to_age` "override scenario defaults"
advanced controls already work (spec.md Assumptions)

**Testing**: `pytest services/bff/tests/` (new integration cases in
`test_bff_lifecycle.py`, mirroring its existing `survival_adjusted` test
block exactly; a handful of new `resolution.py` unit tests), `pytest
apps/streamlit_ui/tests/` (page-import/session-state smoke coverage,
mirroring existing page tests) — existing suites, extended

**Target Platform**: Linux/macOS dev laptop, offline (constitution Principle V)

**Performance Goals**: No material change — `check_run_cost()` is already
documented as path-count-based, independent of generation mode (spec.md
Assumptions); no change to `cost_estimation.py`

**Constraints**: Must reproduce every existing `/simulations` and
`/comparisons/simulated` request's exact current behavior byte-for-byte when
the three new fields are omitted (FR-003, SC-003); must not alter
`resolve_and_run_simulation()`/`resolve_and_compare_simulated()`'s own
already-locked return shapes; a `Deterministic` comparison must remain
completely unaffected (FR-007)

**Scale/Scope**: BFF (`routes/simulations.py`, `routes/comparisons.py`,
`resolution.py`, `schemas.py`) + Streamlit UI editing surface
(`2_Run_Simulation.py`, `3_Compare.py`) + `docs/BRD.md` §6.8/§7. No core
`retirement_planner` package change — both engine functions this feature
calls already exist, are already tested, and keep their exact current
signatures unchanged.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness**: PASS. Historical-bootstrap mode's
  synthetic-placeholder-data caveat (`docs/BRD.md` §6.9) is carried through
  automatically by the existing `figures_used` → `unverified_figure_names`
  pipeline (no new plumbing needed — `ReturnPath.figures_used` already
  includes `HISTORICAL_RETURNS.usage_for_year()`, `verified=False`) and is
  additionally stated explicitly in the new UI control's own help text,
  mirroring `survival_adjusted`'s own disclosed-caveat precedent (FR-006).
- **II. Reproducibility**: PASS. Both new engine calls are already
  seed-deterministic (unchanged, existing, tested functions); no new
  randomness source is introduced by this feature.
- **III. Auditability**: PASS. No new `SourcedFigure` — this feature
  exposes access to an existing cited (if unverified) one
  (`HISTORICAL_RETURNS`), it doesn't create a new figure.
- **IV. Extensibility Through Module Interfaces**: PASS. One new shared
  resolution.py helper, consumed identically by both existing
  `resolve_and_*` functions — mirrors `build_survival_curves()`'s own
  integration shape exactly; zero change to any core `retirement_planner`
  module's public interface.
- **V. Offline-First**: PASS. No runtime network dependency introduced.
- **VI. Performance Budget**: PASS. Explicitly documented as
  generation-mode-independent (spec.md Assumptions); `cost_estimation.py`
  needs no change.

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/026-advanced-simulation-options/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (addendum to bff-api.md)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
services/bff/src/rp_bff/
├── schemas.py
│     # + StressScenarioRequest (shared nested model, magnitude/duration_years/start_plan_year)
├── resolution.py
│     # + generate_configured_return_paths() (dispatch + stress overlay, shared helper)
│     # + invalid_simulation_options_error() (ValueError -> 422 translator)
│     # + imports: GenerationMode, StressScenario, ReturnPath, generate_return_paths,
│     #   generate_historical_bootstrap_paths, apply_stress_scenario (from retirement_planner.simulation)
└── routes/
    ├── simulations.py
    │     # SimulationRequest: + generation_mode, historical_block_length, stress_scenario
    │     # resolve_and_run_simulation(): call the new shared helper instead of
    │     #   generate_return_paths() directly, catch ValueError
    └── comparisons.py
          # ComparisonRequest: + generation_mode, historical_block_length, stress_scenario
          # resolve_and_compare_simulated(): same substitution

apps/streamlit_ui/pages/
├── 2_Run_Simulation.py
│     # "Advanced overrides" expander: + generation-mode selectbox, block-length number_input,
│     #   stress checkbox + magnitude/duration/start-plan-year number_inputs
│     # _build_run_body(): + generation_mode, historical_block_length, conditional stress_scenario
└── 3_Compare.py
      # + new "Advanced overrides" expander (gated: Monte Carlo engine only), same three controls
      # _build_body(): same additions, .get()-based (mirrors survival_adjusted's own Deterministic-safe pattern)

services/bff/tests/integration/test_bff_lifecycle.py   # + generation-mode/stress test block
services/bff/tests/unit/test_resolution.py               # + generate_configured_return_paths() unit tests
apps/streamlit_ui/tests/integration/test_app_pages.py     # existing page-smoke coverage, confirm unaffected
docs/BRD.md   # §6.8 "not yet exposed" language closed; §7 rp-741/rp-2bn follow-on note closed
```

**Structure Decision**: Extends the existing BFF resolution/routes layer and
Streamlit editing surface exactly as `rp-9vl` (survival_adjusted,
`023-probabilistic-death-draws`) did for its own opt-in Monte-Carlo-only
field — no core `retirement_planner` package change, no new scenario schema.
